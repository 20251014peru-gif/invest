# v 20260915-WaveB4  event_dictionary.py — 공시 제목 → Event Family / Type / Version / Urgency 사전.
# AI 0. 규칙에 없으면 OTHER/UNMAPPED. NFKC는 ㆍ를 깨뜨리므로 사용하지 않는다.
DOT_VARIANTS = {"\u318D", "\u00B7", "\u2219", "\uFF65", "\u30FB"}
DOT_CANON = "\u00B7"
VERSION_MARKERS = [
    ("기재정정", "CORRECTION"),("첨부정정", "ATTACHMENT_CORRECTION"),("첨부추가", "ATTACHMENT_CORRECTION"),
    ("발행조건확정", "TERMS_FINAL"),("정정", "CORRECTION"),("철회", "WITHDRAWAL")]
DEFAULT_VERSION = "ORIGINAL"
CHANNEL_MARKERS = ["자율공시", "공정공시", "자회사의 주요경영사항", "안내공시", "약식"]
RULES = [
    dict(type="CONTRACT_CANCEL",family="CONTRACT",groups=[["공급계약","해지"],["공급계약","해제"],["공급계약","취소"]],u="U3"),
    dict(type="SUPPLY_CONTRACT",family="CONTRACT",groups=[["단일판매","공급계약"],["공급계약","체결"]],none=["해지","해제","취소"],u="U2"),
    dict(type="EARNINGS_PRELIMINARY",family="EARNINGS",groups=[["잠정","실적"],["영업","잠정"]],u="U2"),
    dict(type="RIGHTS_OFFERING",family="DILUTION",groups=[["유상증자"]],u="U2"),
    dict(type="CB_ISSUE",family="DILUTION",groups=[["전환사채"]],u="U2"),
    dict(type="BW_ISSUE",family="DILUTION",groups=[["신주인수권부사채"],["신주인수권"]],none=["증서"],u="U2"),
    dict(type="EB_ISSUE",family="DILUTION",groups=[["교환사채"]],u="U2"),
    dict(type="EQUITY_OFFERING_REG",family="DILUTION",groups=[["증권신고서","지분증권"]],none=["효력발생"],u="U2"),
    dict(type="BUYBACK",family="CAPITAL_RETURN",groups=[["자기주식","취득"]],u="U1"),
    dict(type="TREASURY_DISPOSAL",family="CAPITAL_RETURN",groups=[["자기주식","처분"]],u="U1"),
    dict(type="TREASURY_STOCK",family="CAPITAL_RETURN",groups=[["자기주식"]],u="U1"),
    dict(type="FACILITY_INVESTMENT",family="ASSET",groups=[["신규시설투자"],["시설투자"]],u="U1"),
    dict(type="INSIDER_TRADING_PLAN",family="OWNERSHIP",groups=[["임원","주요주주","거래계획"],["특정증권","거래계획"]],u="U1"),
    dict(type="INSIDER_HOLDING",family="OWNERSHIP",groups=[["임원","주요주주","소유상황"],["특정증권","소유상황"]],u="U1"),
    dict(type="MAJOR_HOLDER_5PCT",family="OWNERSHIP",groups=[["대량보유"]],u="U1"),
    dict(type="OWNERSHIP_CONTROL_CHANGE",family="CONTROL",groups=[["최대주주","변경"],["경영권"],["최대주주","양수도"]],u="U2"),
    dict(type="MAJOR_SHAREHOLDER_HOLDING_CHANGE",family="OWNERSHIP",groups=[["최대주주","변동"]],u="U1"),
    dict(type="RUMOR_RESPONSE",family="RUMOR_CHECK",groups=[["풍문","해명"],["보도","해명"]],u="U2"),
    dict(type="INQUIRY_DISCLOSURE",family="RUMOR_CHECK",groups=[["조회공시"]],u="U2"),
    dict(type="LITIGATION",family="LEGAL",groups=[["소송"],["소제기"],["소장"]],u="U2"),
    dict(type="AUDIT_OPINION",family="AUDIT",groups=[["감사의견","거절"],["감사의견","부적정"],["감사의견","한정"],["계속기업"]],u="U3",fast=True),
    dict(type="AUDIT_REPORT",family="PERIODIC",groups=[["감사보고서"]],none=["의견거절","부적정","한정","계속기업"],u="U0"),
    dict(type="DEFAULT",family="SURVIVAL",groups=[["부도"]],u="U3",fast=True),
    dict(type="REHABILITATION",family="SURVIVAL",groups=[["회생절차"],["회생"]],u="U3",fast=True),
    dict(type="BUSINESS_SUSPENSION",family="OPERATION_RISK",groups=[["영업정지"]],u="U3",fast=True),
    dict(type="TRADING_HALT",family="MARKET_ACTION",groups=[["매매거래정지"],["거래정지"]],u="U3",fast=True),
    dict(type="DELISTING",family="MARKET_ACTION",groups=[["상장폐지"]],u="U3",fast=True),
    dict(type="MERGER",family="M&A_CONTROL",groups=[["합병"]],none=["분할"],u="U2"),
    dict(type="SPINOFF",family="CAPITAL_STRUCTURE",groups=[["분할"]],u="U2"),
    dict(type="PROSPECTUS",family="CAPITAL_STRUCTURE",groups=[["투자설명서"]],u="U0"),
    dict(type="REGISTRATION_EFFECTIVE",family="CAPITAL_STRUCTURE",groups=[["효력발생"]],u="U0"),
    dict(type="IR_EVENT",family="PERIODIC",groups=[["기업설명회"],["IR"]],u="U0")]
FALLBACK = dict(type="UNMAPPED", family="OTHER", u="U0")
