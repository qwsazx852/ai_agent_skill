"""
台灣股市股票清單擷取
- 支援上市 (TWSE) 與上櫃 (OTC) 股票
- 支援 FinMind API 取得完整台股清單
"""

import time
import requests
import pandas as pd
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


# 主要上市大型股票清單 (預設觀察池)
# 涵蓋各大產業龍頭 + 熱門成長股
DEFAULT_WATCH_LIST = [
    # 半導體
    "2330", "2303", "2308", "2379", "2454", "3711", "2344", "2449",
    "3034", "2338", "6770", "3443", "2404", "2408", "3533",
    # 電子零組件
    "2317", "2354", "2382", "3231", "2377", "2383", "3008", "2357",
    "2353", "3706", "2365",
    # 電腦及週邊/ODM/OEM
    "2357", "2324", "2356", "3231", "4938", "2395", "2301",
    # 光電/面板
    "2409", "3481", "2475", "2348",
    # 通訊網路
    "2498", "3045", "4904", "2412",
    # 金融保險
    "2882", "2881", "2886", "2884", "2891", "2885", "2892",
    "2883", "5880", "2887", "2888",
    # 生技醫療
    "4711", "4715", "6547", "1730", "4726",
    # 航運
    "2603", "2609", "2615", "2610",
    # 鋼鐵
    "2002", "2006",
    # 建材營造
    "2395", "5534",
    # 食品飲料
    "1216", "1301", "1303", "1326",
    # 電機機械/電動車
    "1590", "2227", "1524",
    # AI/雲端/伺服器
    "3661", "6669", "4977", "3293", "6770",
]


def get_finmind_stock_list(token: str) -> pd.DataFrame:
    """
    呼叫 FinMind API TaiwanStockInfo 取得完整台股清單

    Args:
        token: FinMind API token

    Returns:
        DataFrame with columns: stock_id, stock_name, industry, market, yf_ticker
        過濾條件：只保留 4 碼數字代號、type 為上市或上櫃
    """
    try:
        url = "https://api.finmindtrade.com/api/v4/data"
        params = {
            "dataset": "TaiwanStockInfo",
            "token": token,
        }
        resp = requests.get(url, params=params, timeout=15)
        time.sleep(0.3)

        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") == 200 and data.get("data"):
                df = pd.DataFrame(data["data"])

                # 只保留 4 碼數字代號
                df = df[df["stock_id"].str.match(r"^\d{4}$", na=False)]

                # 過濾 type: 上市 (twse) 或 上櫃 (otc)
                if "type" in df.columns:
                    df = df[df["type"].str.lower().isin(["twse", "otc", "上市", "上櫃"])]

                if df.empty:
                    logger.warning("FinMind TaiwanStockInfo 過濾後無資料")
                    return pd.DataFrame()

                # 額外過濾：排除 ETF、特別股、存託憑證等非一般股
                # 這些通常在 yfinance 找不到資料，會造成大量 error 訊息
                EXCLUDE_KEYWORDS = [
                    "ETF", "基金", "存託", "特別", "受益", "債券",
                    "指數", "期貨", "期信", "不動產", "REITs"
                ]
                if "stock_name" in df.columns:
                    pattern = "|".join(EXCLUDE_KEYWORDS)
                    df = df[~df["stock_name"].str.contains(pattern, na=False)]

                # 排除股票代號以 0 開頭（ETF）或 9 開頭（特殊）
                df = df[~df["stock_id"].str.startswith(("0", "9"), na=False)]

                logger.info(f"FinMind 過濾後有效股票: {len(df)} 檔")

                result = pd.DataFrame()
                result["stock_id"] = df["stock_id"].astype(str)
                result["stock_name"] = df.get("stock_name", df["stock_id"])
                result["industry"] = df.get("industry_category", "未分類")

                # 依 type 決定市場別與 ticker 後綴
                if "type" in df.columns:
                    def _market(t):
                        t = str(t).lower()
                        if t in ("otc", "上櫃"):
                            return "OTC"
                        return "TWSE"

                    def _suffix(t):
                        t = str(t).lower()
                        if t in ("otc", "上櫃"):
                            return ".TWO"
                        return ".TW"

                    result["market"] = df["type"].apply(_market).values
                    result["yf_ticker"] = (
                        df["stock_id"].astype(str) + df["type"].apply(_suffix)
                    ).values
                else:
                    result["market"] = "TWSE"
                    result["yf_ticker"] = df["stock_id"].astype(str) + ".TW"

                result = result.reset_index(drop=True)
                logger.info(f"FinMind 取得台股清單: {len(result)} 檔")
                return result

    except Exception as e:
        logger.warning(f"FinMind TaiwanStockInfo 擷取失敗: {e}")

    return pd.DataFrame()


def get_twse_stock_list() -> pd.DataFrame:
    """
    從台灣證券交易所取得上市股票清單
    Returns DataFrame with columns: 股票代號, 股票名稱, 產業別, 市場別
    """
    try:
        url = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            df = pd.DataFrame(data)
            # 欄位對應
            column_map = {
                "公司代號": "stock_id",
                "公司簡稱": "stock_name",
                "產業別": "industry",
            }
            df = df.rename(columns=column_map)
            if "stock_id" in df.columns:
                df["market"] = "TWSE"
                df["yf_ticker"] = df["stock_id"] + ".TW"
                return df[["stock_id", "stock_name", "industry", "market", "yf_ticker"]]
    except Exception as e:
        logger.warning(f"TWSE API 失敗: {e}")

    return _get_default_stock_df("TWSE")


def get_otc_stock_list() -> pd.DataFrame:
    """
    從證券櫃檯買賣中心取得上櫃股票清單
    """
    try:
        url = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            df = pd.DataFrame(data)
            if not df.empty:
                df["market"] = "OTC"
                if "SecuritiesCompanyCode" in df.columns:
                    df["stock_id"] = df["SecuritiesCompanyCode"]
                    df["stock_name"] = df.get("CompanyName", "")
                    df["industry"] = df.get("Industry", "")
                    df["yf_ticker"] = df["stock_id"] + ".TWO"
                    return df[["stock_id", "stock_name", "industry", "market", "yf_ticker"]]
    except Exception as e:
        logger.warning(f"OTC API 失敗: {e}")

    return _get_default_stock_df("OTC")


def _get_default_stock_df(market: str) -> pd.DataFrame:
    """回傳預設股票 DataFrame"""
    stocks = []
    for sid in DEFAULT_WATCH_LIST:
        suffix = ".TW" if market == "TWSE" else ".TWO"
        stocks.append({
            "stock_id": sid,
            "stock_name": sid,
            "industry": "未分類",
            "market": market,
            "yf_ticker": sid + suffix,
        })
    return pd.DataFrame(stocks)


def get_combined_stock_list(
    include_otc: bool = True,
    custom_list: Optional[List[str]] = None,
    max_stocks: int = 300,
    finmind_token: str = ""
) -> pd.DataFrame:
    """
    取得合併股票清單

    Args:
        include_otc: 是否包含上櫃股票
        custom_list: 自訂股票代號清單
        max_stocks: 最大股票數量
        finmind_token: FinMind API token（有則優先用 FinMind 取得完整清單）

    Returns:
        DataFrame with stock information
    """
    if custom_list:
        rows = []
        for sid in custom_list:
            rows.append({
                "stock_id": sid,
                "stock_name": sid,
                "industry": "自訂",
                "market": "TWSE",
                "yf_ticker": sid + ".TW",
            })
        return pd.DataFrame(rows)

    # 若有 FinMind token，優先使用 FinMind 取得完整清單
    if finmind_token:
        finmind_df = get_finmind_stock_list(finmind_token)
        if not finmind_df.empty:
            finmind_df = finmind_df.drop_duplicates(subset=["stock_id"])
            default_ids = set(DEFAULT_WATCH_LIST)
            priority = finmind_df[finmind_df["stock_id"].isin(default_ids)]
            others = finmind_df[~finmind_df["stock_id"].isin(default_ids)]
            result = pd.concat([priority, others]).head(max_stocks)
            result = result.reset_index(drop=True)
            logger.info(f"最終股票池 (FinMind): {len(result)} 檔")
            return result

    # 取得上市股票（fallback：TWSE + OTC 公開 API）
    twse_df = get_twse_stock_list()
    logger.info(f"取得上市股票: {len(twse_df)} 檔")

    dfs = [twse_df]

    if include_otc:
        otc_df = get_otc_stock_list()
        logger.info(f"取得上櫃股票: {len(otc_df)} 檔")
        dfs.append(otc_df)

    combined = pd.concat(dfs, ignore_index=True)

    # 過濾：只保留數字型股票代號 (4碼為主)
    combined = combined[combined["stock_id"].str.match(r"^\d{4}$", na=False)]
    combined = combined.drop_duplicates(subset=["stock_id"])

    # 限制數量（優先使用預設觀察清單）
    default_ids = set(DEFAULT_WATCH_LIST)
    priority = combined[combined["stock_id"].isin(default_ids)]
    others = combined[~combined["stock_id"].isin(default_ids)]

    result = pd.concat([priority, others]).head(max_stocks)
    result = result.reset_index(drop=True)

    logger.info(f"最終股票池: {len(result)} 檔")
    return result


def get_industry_map() -> Dict[str, str]:
    """
    回傳股票代號 -> 產業別 的對應字典
    """
    # 手工定義主要台股產業分類
    industry_map = {
        # 半導體
        "2330": "半導體", "2303": "半導體", "2308": "半導體",
        "2379": "半導體", "2454": "半導體", "3711": "半導體",
        "2344": "半導體", "2449": "半導體", "3034": "半導體",
        "2338": "半導體", "6770": "半導體", "3443": "半導體",
        "2404": "半導體", "2408": "半導體", "3533": "半導體",
        # 電子零組件
        "2317": "電子零組件", "2354": "電子零組件", "2382": "電子零組件",
        "3231": "電子零組件", "2377": "電子零組件", "2383": "電子零組件",
        "3008": "電子零組件", "2357": "電子零組件",
        # AI/伺服器
        "3661": "AI/雲端", "6669": "AI/雲端", "4977": "AI/雲端",
        "3293": "AI/雲端",
        # 金融
        "2882": "金融保險", "2881": "金融保險", "2886": "金融保險",
        "2884": "金融保險", "2891": "金融保險", "2885": "金融保險",
        "2892": "金融保險", "2883": "金融保險", "5880": "金融保險",
        # 航運
        "2603": "航運", "2609": "航運", "2615": "航運", "2610": "航運",
        # 生技
        "4711": "生技醫療", "4715": "生技醫療", "6547": "生技醫療",
        "1730": "生技醫療", "4726": "生技醫療",
        # 傳產
        "2002": "鋼鐵", "2006": "鋼鐵",
        "1216": "食品", "1301": "塑化", "1303": "塑化", "1326": "塑化",
        "2412": "電信", "3045": "電信", "4904": "電信",
        # 電動車
        "1590": "電機機械", "2227": "電動車", "1524": "電機機械",
    }
    return industry_map
