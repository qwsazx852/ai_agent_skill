"""
股票篩選主控模組
整合所有分析模組，執行每日篩選流程

執行流程:
1. 取得股票清單
2. 批次下載價格資料
3. 技術分析
4. 基本面分析 (FinMind API)
5. 籌碼分析 (FinMind API)
6. 產業分析
7. 綜合評分
8. 排名輸出
9. 儲存結果
10. 發送通知
"""

import os
import json
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import warnings
warnings.filterwarnings("ignore")

from .config import config
from .data.tw_stock_list import get_combined_stock_list, get_industry_map
from .data.fetcher import (
    fetch_batch_price_data,
    fetch_finmind_institutional,
    fetch_finmind_financials,
    fetch_finmind_revenue,
    get_mock_institutional_data,
    get_mock_financial_data,
)
from .analysis.technical import analyze_technical
from .analysis.fundamental import analyze_fundamental, parse_finmind_financials, parse_finmind_revenue
from .analysis.institutional import analyze_institutional, parse_finmind_institutional
from .analysis.industry import (
    calculate_industry_performance,
    get_industry_score,
    get_hot_industries,
    identify_rotation_opportunities,
)
from .analysis.scorer import score_stock, rank_stocks, StockScore

logger = logging.getLogger(__name__)


class StockScreener:
    """台灣股市每日篩選系統"""

    def __init__(self, cfg=None):
        self.cfg = cfg or config
        self.results: List[StockScore] = []
        self.industry_stats: Dict = {}
        self.screening_date = datetime.now().strftime("%Y-%m-%d")
        self.screening_time = datetime.now().strftime("%H:%M:%S")

    def run(
        self,
        use_mock_data: bool = False,
        custom_stocks: Optional[List[str]] = None,
        top_n: Optional[int] = None
    ) -> List[Dict]:
        """
        執行完整篩選流程

        Args:
            use_mock_data: 是否使用模擬資料 (測試用)
            custom_stocks: 自訂股票清單
            top_n: 輸出前N名

        Returns:
            排名後的股票資料清單
        """
        top_n = top_n or self.cfg.TOP_N
        logger.info(f"🚀 開始每日股票篩選 - {self.screening_date}")

        # ─── Step 1: 取得股票清單 ──────────────────────────────
        logger.info("📋 Step 1: 取得股票清單...")
        stock_df = get_combined_stock_list(
            custom_list=custom_stocks,
            max_stocks=self.cfg.MAX_STOCKS
        )
        industry_map = get_industry_map()

        logger.info(f"股票池: {len(stock_df)} 檔")

        # 合併產業資訊
        stock_df["industry"] = stock_df["stock_id"].map(
            lambda x: industry_map.get(x, stock_df.loc[
                stock_df["stock_id"] == x, "industry"
            ].values[0] if x in stock_df["stock_id"].values else "其他")
        )

        # ─── Step 2: 下載價格資料 ──────────────────────────────
        logger.info("📥 Step 2: 下載股票價格資料...")
        tickers = stock_df["yf_ticker"].tolist()

        if use_mock_data:
            price_data = self._generate_mock_price_data(stock_df)
        else:
            price_data = fetch_batch_price_data(
                tickers,
                days=self.cfg.LOOKBACK_DAYS,
                batch_size=20,
                delay=0.5
            )

        logger.info(f"成功下載 {len(price_data)}/{len(tickers)} 檔價格資料")

        # ─── Step 3: 產業趨勢分析 ──────────────────────────────
        logger.info("🏭 Step 3: 分析產業趨勢...")
        stock_industry_map = {}
        for _, row in stock_df.iterrows():
            stock_id = row["stock_id"]
            ticker = row["yf_ticker"]
            stock_industry_map[stock_id] = industry_map.get(stock_id, row.get("industry", "其他"))

        self.industry_stats = calculate_industry_performance(
            price_data, stock_industry_map
        )

        hot_industries = get_hot_industries(self.industry_stats)
        rotation_signals = identify_rotation_opportunities(self.industry_stats)

        logger.info(f"分析 {len(self.industry_stats)} 個產業")
        if hot_industries:
            top_ind = hot_industries[0]
            logger.info(f"最強產業: {top_ind['industry']} ({top_ind['avg_ret_5d']:+.1f}%)")

        # ─── Step 4: 個股分析 ──────────────────────────────────
        logger.info("🔍 Step 4: 逐檔個股分析...")
        scored_stocks = []
        analyzed_count = 0

        # 使用 FinMind API 日期
        api_date = (datetime.now()).strftime("%Y-%m-%d")

        for _, row in stock_df.iterrows():
            stock_id = row["stock_id"]
            stock_name = row.get("stock_name", stock_id)
            industry = industry_map.get(stock_id, row.get("industry", "其他"))
            market = row.get("market", "TWSE")
            ticker = row["yf_ticker"]

            # 取得價格資料
            price_df = price_data.get(ticker)
            if price_df is None or len(price_df) < 20:
                continue

            # --- 技術分析 ---
            tech_result = analyze_technical(price_df)

            # --- 基本面分析 ---
            if use_mock_data:
                fin_data = get_mock_financial_data(stock_id)
            else:
                fin_data = self._fetch_fundamental_data(stock_id, api_date)

            fund_result = analyze_fundamental(fin_data)

            # --- 籌碼分析 ---
            if use_mock_data:
                inst_data = get_mock_institutional_data(stock_id)
            else:
                inst_data = self._fetch_institutional_data(stock_id, api_date)

            inst_result = analyze_institutional(inst_data)

            # --- 產業分析 ---
            stock_ret_20d = tech_result.get("indicators", {}).get("change_20d", 0)
            if stock_ret_20d:
                stock_ret_20d /= 100  # 轉為小數

            ind_result = get_industry_score(
                stock_id, industry,
                self.industry_stats,
                stock_ret_20d
            )

            # --- 綜合評分 ---
            stock_score = score_stock(
                stock_id=stock_id,
                stock_name=stock_name,
                industry=industry,
                market=market,
                technical_result=tech_result,
                fundamental_result=fund_result,
                institutional_result=inst_result,
                industry_result=ind_result,
                weights={
                    "technical": self.cfg.WEIGHT_TECHNICAL,
                    "fundamental": self.cfg.WEIGHT_FUNDAMENTAL,
                    "institutional": self.cfg.WEIGHT_INSTITUTIONAL,
                    "industry": self.cfg.WEIGHT_INDUSTRY,
                }
            )

            scored_stocks.append(stock_score)
            analyzed_count += 1

            if analyzed_count % 20 == 0:
                logger.info(f"  已分析 {analyzed_count}/{len(stock_df)} 檔...")

        logger.info(f"✅ 分析完成: {analyzed_count} 檔股票")

        # ─── Step 5: 排名與篩選 ────────────────────────────────
        logger.info("🏆 Step 5: 排名與篩選...")
        ranked = rank_stocks(scored_stocks)
        self.results = ranked

        top_stocks = [s.to_dict() for s in ranked[:top_n]]

        logger.info(f"篩選完成，輸出前 {top_n} 名")
        if top_stocks:
            best = top_stocks[0]
            logger.info(f"🥇 第一名: {best['stock_id']} {best['stock_name']} "
                       f"({best['composite_score']:.1f}分/{best['grade']})")

        # ─── Step 6: 儲存結果 ──────────────────────────────────
        output = {
            "date": self.screening_date,
            "time": self.screening_time,
            "total_analyzed": analyzed_count,
            "hot_industries": hot_industries,
            "industry_signals": rotation_signals,
            "top_stocks": top_stocks,
            "all_stocks": [s.to_dict() for s in ranked],
        }

        self._save_results(output)

        logger.info(f"📁 結果已儲存至 {self.cfg.RESULTS_FILE}")
        return top_stocks

    def _fetch_fundamental_data(self, stock_id: str, date: str) -> Dict:
        """擷取基本面資料"""
        if not self.cfg.FINMIND_API_TOKEN:
            return get_mock_financial_data(stock_id)

        try:
            fin_df = fetch_finmind_financials(stock_id, self.cfg.FINMIND_API_TOKEN)
            rev_df = fetch_finmind_revenue(stock_id, self.cfg.FINMIND_API_TOKEN)

            data = {}
            if fin_df is not None:
                data.update(parse_finmind_financials(fin_df))
            if rev_df is not None:
                data.update(parse_finmind_revenue(rev_df))

            time.sleep(0.2)  # API rate limit
            return data if data else get_mock_financial_data(stock_id)
        except Exception as e:
            logger.debug(f"基本面資料擷取失敗 {stock_id}: {e}")
            return get_mock_financial_data(stock_id)

    def _fetch_institutional_data(self, stock_id: str, date: str) -> Dict:
        """擷取籌碼資料"""
        if not self.cfg.FINMIND_API_TOKEN:
            return get_mock_institutional_data(stock_id)

        try:
            inst_df = fetch_finmind_institutional(
                stock_id, date, self.cfg.FINMIND_API_TOKEN
            )

            if inst_df is not None:
                data = parse_finmind_institutional(inst_df)
                time.sleep(0.2)
                return data if data else get_mock_institutional_data(stock_id)
        except Exception as e:
            logger.debug(f"籌碼資料擷取失敗 {stock_id}: {e}")

        return get_mock_institutional_data(stock_id)

    def _generate_mock_price_data(self, stock_df) -> Dict:
        """產生模擬價格資料（測試用）"""
        import pandas as pd
        import numpy as np

        mock_data = {}
        base_date = pd.date_range(end=datetime.now(), periods=120, freq="B")

        for _, row in stock_df.iterrows():
            ticker = row["yf_ticker"]
            rng = np.random.default_rng(seed=hash(ticker) % 10000)

            # 模擬隨機漫步股價
            initial_price = rng.uniform(20, 500)
            returns = rng.normal(0.001, 0.02, size=120)
            prices = initial_price * (1 + pd.Series(returns)).cumprod()
            prices_arr = prices.values  # 轉為 numpy array 避免索引不匹配

            df = pd.DataFrame({
                "open": prices_arr * rng.uniform(0.99, 1.0, size=120),
                "high": prices_arr * rng.uniform(1.0, 1.03, size=120),
                "low": prices_arr * rng.uniform(0.97, 1.0, size=120),
                "close": prices_arr,
                "volume": rng.uniform(1000, 50000, size=120),
            }, index=base_date)

            mock_data[ticker] = df

        return mock_data

    def _save_results(self, output: Dict) -> None:
        """儲存篩選結果"""
        os.makedirs(self.cfg.RESULTS_DIR, exist_ok=True)

        # 儲存最新結果
        with open(self.cfg.RESULTS_FILE, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2, default=str)

        # 更新歷史記錄
        history = []
        if os.path.exists(self.cfg.HISTORY_FILE):
            try:
                with open(self.cfg.HISTORY_FILE, "r", encoding="utf-8") as f:
                    history = json.load(f)
            except Exception:
                history = []

        # 只保留最近30天
        history.append({
            "date": output["date"],
            "time": output["time"],
            "total_analyzed": output["total_analyzed"],
            "top3": [
                {
                    "stock_id": s["stock_id"],
                    "stock_name": s["stock_name"],
                    "score": s["composite_score"],
                    "grade": s["grade"],
                }
                for s in output["top_stocks"][:3]
            ]
        })
        history = history[-30:]

        with open(self.cfg.HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2, default=str)

    def notify(self, top_stocks: List[Dict], dashboard_url: str = "") -> bool:
        """
        傳送 Telegram 通知

        Args:
            top_stocks: 篩選結果
            dashboard_url: Dashboard 網址

        Returns:
            是否成功
        """
        from .notifier.telegram import TelegramNotifier

        notifier = TelegramNotifier(
            bot_token=self.cfg.TELEGRAM_BOT_TOKEN,
            chat_id=self.cfg.TELEGRAM_CHAT_ID,
        )

        hot_industries = get_hot_industries(self.industry_stats)
        rotation_signals = identify_rotation_opportunities(self.industry_stats)

        return notifier.send_screening_report(
            top_stocks=top_stocks,
            hot_industries=hot_industries,
            industry_signals=rotation_signals,
            date=self.screening_date,
            dashboard_url=dashboard_url,
        )
