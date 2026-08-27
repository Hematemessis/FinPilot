"""Core package for the FinPilot portfolio-advisor showcase."""

from .agent import AdvisorReport, PortfolioAdvisorAgent
from .china_market_data import (
    DEFAULT_CHINA_ALLOCATION_SYMBOLS,
    MARKET_SOURCES,
    SECURITY_MASTER,
    ChinaSecurity,
    MarketSource,
    load_eastmoney_prices,
    research_source_plan,
)
from .risk import RiskAnswers, RiskProfile, assess_risk
from .stock_research import (
    CompanyResearchCard,
    CompanyResearchSnapshot,
    StockResearchAgent,
    ValuationInputs,
    assess_valuation,
    calculate_pe,
    make_demo_company_snapshot,
)

__all__ = [
    "AdvisorReport",
    "ChinaSecurity",
    "DEFAULT_CHINA_ALLOCATION_SYMBOLS",
    "MARKET_SOURCES",
    "MarketSource",
    "PortfolioAdvisorAgent",
    "RiskAnswers",
    "RiskProfile",
    "CompanyResearchCard",
    "CompanyResearchSnapshot",
    "StockResearchAgent",
    "ValuationInputs",
    "assess_valuation",
    "assess_risk",
    "calculate_pe",
    "load_eastmoney_prices",
    "make_demo_company_snapshot",
    "research_source_plan",
    "SECURITY_MASTER",
]
