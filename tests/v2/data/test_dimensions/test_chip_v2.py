"""Extended tests for ChipFetcher — covering all branches."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd  # type: ignore[import-untyped]

from quant_lab.core.data.dimensions.chip import ChipFetcher


class TestChipFetcherExtended:
    def test_profit_ratio_over_80(self) -> None:
        with patch("quant_lab.core.data.dimensions.chip.ak") as mock_ak:
            mock_ak.stock_cyq_em.return_value = pd.DataFrame(
                {"获利比例": [85.0], "平均成本": [25.0], "90%集中度": [15.0]}
            )
            fetcher = ChipFetcher()
            result = fetcher.fetch("000001", "平安银行")
            assert result["chip_signal"] == "获利盘过多，注意回调风险"

    def test_profit_ratio_50_to_80(self) -> None:
        with patch("quant_lab.core.data.dimensions.chip.ak") as mock_ak:
            mock_ak.stock_cyq_em.return_value = pd.DataFrame(
                {"获利比例": [65.0], "平均成本": [25.0]}
            )
            fetcher = ChipFetcher()
            result = fetcher.fetch("000001", "平安银行")
            assert result["chip_signal"] == "筹码偏集中，支撑较强"

    def test_profit_ratio_below_20(self) -> None:
        with patch("quant_lab.core.data.dimensions.chip.ak") as mock_ak:
            mock_ak.stock_cyq_em.return_value = pd.DataFrame(
                {"获利比例": [15.0], "平均成本": [25.0]}
            )
            fetcher = ChipFetcher()
            result = fetcher.fetch("000001", "平安银行")
            assert result["chip_signal"] == "套牢盘较重，下方有支撑"

    def test_profit_ratio_balanced(self) -> None:
        with patch("quant_lab.core.data.dimensions.chip.ak") as mock_ak:
            mock_ak.stock_cyq_em.return_value = pd.DataFrame(
                {"获利比例": [35.0], "平均成本": [25.0]}
            )
            fetcher = ChipFetcher()
            result = fetcher.fetch("000001", "平安银行")
            assert result["chip_signal"] == "筹码分布均衡"

    def test_no_profit_ratio_column(self) -> None:
        with patch("quant_lab.core.data.dimensions.chip.ak") as mock_ak:
            mock_ak.stock_cyq_em.return_value = pd.DataFrame(
                {"平均成本": [25.0]}
            )
            fetcher = ChipFetcher()
            with patch.object(fetcher, "_fetch_from_datacenter", return_value=None):
                result = fetcher.fetch("000001", "平安银行")
                assert result["chip_signal"] == "数据暂不可用"

    def test_no_avg_cost_column(self) -> None:
        with patch("quant_lab.core.data.dimensions.chip.ak") as mock_ak:
            mock_ak.stock_cyq_em.return_value = pd.DataFrame(
                {"获利比例": [50.0]}
            )
            fetcher = ChipFetcher()
            result = fetcher.fetch("000001", "平安银行")
            assert result["chip_profit_ratio_raw"] == 50.0
            assert "chip_avg_cost" not in result

    def test_concentration_columns(self) -> None:
        with patch("quant_lab.core.data.dimensions.chip.ak") as mock_ak:
            mock_ak.stock_cyq_em.return_value = pd.DataFrame(
                {
                    "获利比例": [50.0],
                    "平均成本": [25.0],
                    "90%成本集中度": [15.0],
                    "70%成本集中度": [10.0],
                }
            )
            fetcher = ChipFetcher()
            result = fetcher.fetch("000001", "平安银行")
            assert "chip_concentration_90" in result
            assert "chip_concentration_70" in result

    def test_datacenter_fallback(self) -> None:
        with patch("quant_lab.core.data.dimensions.chip.ak") as mock_ak:
            mock_ak.stock_cyq_em.return_value = pd.DataFrame()

            fetcher = ChipFetcher()
            with patch.object(
                fetcher,
                "_fetch_from_datacenter",
                return_value={
                    "avg_cost": "25.0",
                    "current_price": "28.0",
                    "avg_cost_20d": "24.5",
                    "avg_cost_60d": "23.0",
                },
            ):
                result = fetcher.fetch("000001", "平安银行")
                assert "chip_avg_cost" in result
                assert "chip_signal" in result
                assert "chip_concentration_70" in result
                assert "chip_concentration_90" in result

    def test_datacenter_price_above_cost_large(self) -> None:
        with patch("quant_lab.core.data.dimensions.chip.ak") as mock_ak:
            mock_ak.stock_cyq_em.return_value = pd.DataFrame()
            fetcher = ChipFetcher()
            with patch.object(
                fetcher,
                "_fetch_from_datacenter",
                return_value={
                    "avg_cost": "20.0",
                    "current_price": "25.0",
                },
            ):
                result = fetcher.fetch("000001", "平安银行")
                assert "高于主力成本" in result.get("chip_signal", "")

    def test_datacenter_price_slightly_above(self) -> None:
        with patch("quant_lab.core.data.dimensions.chip.ak") as mock_ak:
            mock_ak.stock_cyq_em.return_value = pd.DataFrame()
            fetcher = ChipFetcher()
            with patch.object(
                fetcher,
                "_fetch_from_datacenter",
                return_value={
                    "avg_cost": "25.0",
                    "current_price": "26.0",
                },
            ):
                result = fetcher.fetch("000001", "平安银行")
                assert "略高于主力成本" in result.get("chip_signal", "")

    def test_datacenter_near_cost(self) -> None:
        with patch("quant_lab.core.data.dimensions.chip.ak") as mock_ak:
            mock_ak.stock_cyq_em.return_value = pd.DataFrame()
            fetcher = ChipFetcher()
            with patch.object(
                fetcher,
                "_fetch_from_datacenter",
                return_value={
                    "avg_cost": "25.0",
                    "current_price": "24.0",
                },
            ):
                result = fetcher.fetch("000001", "平安银行")
                assert "接近主力成本" in result.get("chip_signal", "")

    def test_datacenter_below_cost(self) -> None:
        with patch("quant_lab.core.data.dimensions.chip.ak") as mock_ak:
            mock_ak.stock_cyq_em.return_value = pd.DataFrame()
            fetcher = ChipFetcher()
            with patch.object(
                fetcher,
                "_fetch_from_datacenter",
                return_value={
                    "avg_cost": "30.0",
                    "current_price": "25.0",
                },
            ):
                result = fetcher.fetch("000001", "平安银行")
                assert "低于主力成本" in result.get("chip_signal", "")

    def test_datacenter_no_cost(self) -> None:
        with patch("quant_lab.core.data.dimensions.chip.ak") as mock_ak:
            mock_ak.stock_cyq_em.return_value = pd.DataFrame()
            fetcher = ChipFetcher()
            with patch.object(
                fetcher,
                "_fetch_from_datacenter",
                return_value={"avg_cost": None},
            ):
                result = fetcher.fetch("000001", "平安银行")
                assert result["chip_signal"] == "数据暂不可用"

    def test_datacenter_exception(self) -> None:
        with patch("quant_lab.core.data.dimensions.chip.ak") as mock_ak:
            mock_ak.stock_cyq_em.return_value = pd.DataFrame()
            fetcher = ChipFetcher()
            with patch.object(
                fetcher,
                "_fetch_from_datacenter",
                side_effect=Exception("network error"),
            ):
                result = fetcher.fetch("000001", "平安银行")
                assert result["chip_signal"] == "数据暂不可用"

    def test_summary_with_signal(self) -> None:
        with patch("quant_lab.core.data.dimensions.chip.ak") as mock_ak:
            mock_ak.stock_cyq_em.return_value = pd.DataFrame(
                {"获利比例": [85.0], "平均成本": [25.0]}
            )
            fetcher = ChipFetcher()
            result = fetcher.fetch("000001", "平安银行")
            assert "获利85.0%" in result["chip_summary"]
            assert "均价25.00" in result["chip_summary"]

    def test_summary_no_parts(self) -> None:
        with patch("quant_lab.core.data.dimensions.chip.ak") as mock_ak:
            mock_ak.stock_cyq_em.return_value = pd.DataFrame()
            fetcher = ChipFetcher()
            with patch.object(
                fetcher,
                "_fetch_from_datacenter",
                return_value=None,
            ):
                result = fetcher.fetch("000001", "平安银行")
                assert result["chip_summary"] == "筹码数据不可用"


class TestFetchFromDatacenter:
    def test_datacenter_success(self) -> None:
        fetcher = ChipFetcher()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": {
                "data": [
                    {
                        "PRIME_COST": "25.0",
                        "PRIME_COST_20DAYS": "24.5",
                        "PRIME_COST_60DAYS": "23.0",
                        "CLOSE_PRICE": "28.0",
                        "TURNOVERRATE": "3.5",
                    }
                ]
            }
        }
        with patch("requests.Session") as mock_session_cls:
            mock_session = MagicMock()
            mock_session.get.return_value = mock_response
            mock_session_cls.return_value = mock_session
            result = fetcher._fetch_from_datacenter("000001")
            assert result is not None
            assert result["avg_cost"] == "25.0"
            assert result["current_price"] == "28.0"

    def test_datacenter_no_data(self) -> None:
        fetcher = ChipFetcher()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": {"data": []}}
        with patch("requests.Session") as mock_session_cls:
            mock_session = MagicMock()
            mock_session.get.return_value = mock_response
            mock_session_cls.return_value = mock_session
            result = fetcher._fetch_from_datacenter("000001")
            assert result is None

    def test_datacenter_http_error(self) -> None:
        fetcher = ChipFetcher()
        mock_response = MagicMock()
        mock_response.status_code = 500
        with patch("requests.Session") as mock_session_cls:
            mock_session = MagicMock()
            mock_session.get.return_value = mock_response
            mock_session_cls.return_value = mock_session
            result = fetcher._fetch_from_datacenter("000001")
            assert result is None

    def test_datacenter_exception(self) -> None:
        fetcher = ChipFetcher()
        with patch("requests.Session") as mock_session_cls:
            mock_session = MagicMock()
            mock_session.get.side_effect = Exception("network error")
            mock_session_cls.return_value = mock_session
            result = fetcher._fetch_from_datacenter("000001")
            assert result is None

    def test_datacenter_no_result_key(self) -> None:
        fetcher = ChipFetcher()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        with patch("requests.Session") as mock_session_cls:
            mock_session = MagicMock()
            mock_session.get.return_value = mock_response
            mock_session_cls.return_value = mock_session
            result = fetcher._fetch_from_datacenter("000001")
            assert result is None
