from enum import Enum


class InstrumentType(str, Enum):
    EQ = "equity"
    ETF = "etf"
    MF = "mutual_fund"
    REIT = "reit"
    INVIT = "invit"
    GSEC = "gsec"
    NCD = "ncd"
    SGB = "sgb"
    FUT = "futures"
    OPT = "options"
    CUR = "currency"
    COM = "commodity"


class TrxTypeEnum(str, Enum):
    BUY = "buy"
    SELL = "sell"


INSTRUMENT_LABELS: dict[InstrumentType, str] = {
    InstrumentType.EQ: "Equity",
    InstrumentType.ETF: "Exchange Traded Fund",
    InstrumentType.MF: "Mutual Fund",
    InstrumentType.REIT: "Real Estate Investment Trust",
    InstrumentType.INVIT: "Infrastructure Investment Trust",
    InstrumentType.GSEC: "Government Security",
    InstrumentType.NCD: "Non-Convertible Debenture",
    InstrumentType.SGB: "Sovereign Gold Bond",
    InstrumentType.FUT: "Futures",
    InstrumentType.OPT: "Options",
    InstrumentType.CUR: "Currency",
    InstrumentType.COM: "Commodity",
}
