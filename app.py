import streamlit as st
import pandas as pd
import datetime
import random
import os
import requests
import json
import logging
from crawler import BillCrawler
from openai import OpenAI
from config import OPENAI_API_KEY, KEYWORDS
import pathlib
from bs4 import BeautifulSoup

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 심사 진행 단계에 따른 배지 클래스 반환 함수
def get_status_badge_class(status):
    """
    심사 진행 단계에 따른 배지 클래스를 반환하는 함수
    
    Args:
        status: 심사 진행 단계 문자열
    
    Returns:
        str: 배지 클래스명
    """
    if status is None:
        return "status-기타"
        
    if "발의" in status:
        return "status-발의"
    elif "소관위" in status:
        return "status-소관위"
    elif "법사위" in status:
        return "status-법사위"
    elif "본회의" in status:
        return "status-본회의"
    elif "정부이송" in status:
        return "status-정부이송"
    elif "공포" in status:
        return "status-공포"
    else:
        return "status-기타"

# 웹 스크래핑을 통해 의안 내용 가져오기
def get_bill_content_from_web(detail_link):
    """
    웹 스크래핑을 통해 의안 상세 내용을 가져오는 함수
    
    Args:
        detail_link: 의안 상세 정보 링크
    
    Returns:
        str: 의안 내용 텍스트
    """
    try:
        logger.info(f"웹 스크래핑 시작: {detail_link}")
        
        # 웹 페이지 요청
        response = requests.get(detail_link)
        if response.status_code != 200:
            logger.error(f"웹 페이지 요청 실패: {response.status_code}")
            return ""
        
        # HTML 파싱
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 의안 내용 추출 시도
        content = ""
        
        # 1. 제안이유 및 주요내용 섹션 찾기
        reason_section = soup.find('div', {'class': 'subti01'})
        if reason_section and reason_section.get_text().strip() == "제안이유 및 주요내용":
            content_div = reason_section.find_next('div', {'class': 'text'})
            if content_div:
                content = content_div.get_text().strip()
                logger.info("제안이유 및 주요내용 섹션에서 내용을 찾았습니다.")
        
        # 2. 내용이 없으면 다른 섹션 시도
        if not content:
            # 다양한 클래스나 ID로 시도
            content_sections = soup.select('.textType02, .text, #summaryContentDiv')
            for section in content_sections:
                text = section.get_text().strip()
                if text:
                    content = text
                    logger.info(f"대체 섹션에서 내용을 찾았습니다: {section.get('class') or section.get('id')}")
                    break
        
        logger.info(f"웹 스크래핑으로 추출한 내용 길이: {len(content)}자")
        return content
        
    except Exception as e:
        logger.error(f"웹 스크래핑 중 오류 발생: {str(e)}")
        return ""



# 의안 분석 함수
def analyze_bill_content(title, bill_no, detail_link=None):
    """
    OpenAI API를 사용하여 의안 내용을 분석하는 함수
    
    Args:
        title: 의안 제목
        bill_no: 의안 번호
        detail_link: 의안 상세 정보 링크
    
    Returns:
        dict: 분석 결과를 담은 사전
    """
    try:
        if not OPENAI_API_KEY:
            logger.warning("OpenAI API 키가 설정되지 않아 모의 분석 결과를 반환합니다.")
            return get_mock_analysis(title)
            
        # OpenAI API 호출
        client = OpenAI(api_key=OPENAI_API_KEY)
        
        # 의안 상세 내용 가져오기
        bill_content = ""
        if detail_link:
            try:
                logger.info(f"의안 상세 정보를 가져오는 중: {detail_link}")
                
                # 1. API를 통한 시도
                crawler = BillCrawler()
                bill_id = detail_link.split("BILL_ID=")[-1] if "BILL_ID=" in detail_link else None
                if bill_id:
                    bill_details = crawler.get_bill_details(bill_id=bill_id)
                    
                    # 의안 제안이유 및 주요내용
                    bill_content = bill_details.get("DETAIL_CONTENT", "") or bill_details.get("PROPOSER_COMMENT", "")
                    # 내용이 없으면 이유도 확인
                    if not bill_content:
                        bill_content = bill_details.get("SUBMIT_REASON", "")
                
                # 2. API에서 내용을 가져오지 못했으면 웹 스크래핑 시도
                if not bill_content and detail_link:
                    logger.info("API에서 의안 내용을 가져오지 못했습니다. 웹 스크래핑을 시도합니다.")
                    bill_content = get_bill_content_from_web(detail_link)
                        
                logger.info(f"의안 내용 길이: {len(bill_content) if bill_content else 0}자")
            except Exception as e:
                logger.error(f"의안 상세 내용을 가져오는 중 오류 발생: {str(e)}")
        
        # 프롬프트 구성
        prompt = f"""
        다음은 국회 의안정보입니다:
        
        제목: {title}
        의안번호: {bill_no}
        의안 내용: {bill_content if bill_content else "상세 내용이 제공되지 않았습니다."}
        
        이 의안에 대해 다음 형식으로 분석해주세요:
        
        1. 한 줄 요약: [의안의 핵심 내용을 한 문장으로 쉽게 표현하여 요약]
        2. 주요 내용: [의안의 주요 내용 간단히 중요한 부분을 요약하여 설명]
        3. SK이노베이션 영향:
           - 영향도: [높음/중간/낮음]
           - 영향 분야: [ESG, 환경, 안전, 경영, 생산, 연구개발 등 관련 분야]
           - 주요 영향 세부 사항: [영향 내용 3가지 나열]
        
        JSON 형식으로 응답해주세요.
        """
        
        # API 호출
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "당신은 대외협력팀 전문가이자 SK이노베이션 사업 분석가입니다."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        
        # 응답 파싱
        result = json.loads(response.choices[0].message.content)
        
        # 응답 로깅
        logger.info(f"OpenAI API 응답: {result}")
        
        # 필요한 형식으로 변환 - 수정된 부분
        analysis = {}
        
        # 로그를 확인했을 때 응답 형식이 두 가지로 나타남
        # 형식 1: {'한 줄 요약': '...', '주요 내용': '...', 'SK이노베이션 영향': {...}}
        # 형식 2: {'summary': '...', 'main_content': '...', 'SK_innovation_impact': {...}}
        
        if "한 줄 요약" in result:
            # 형식 1 처리
            analysis = {
                "summary": result.get("한 줄 요약", "분석 정보가 없습니다."),
                "content": result.get("주요 내용", "분석 정보가 없습니다."),
                "impact": {
                    "level": result.get("SK이노베이션 영향", {}).get("영향도", "중간"),
                    "areas": result.get("SK이노베이션 영향", {}).get("영향 분야", ["정보 없음"]),
                    "details": result.get("SK이노베이션 영향", {}).get("주요 영향 세부 사항", ["정보 없음"])
                }
            }
        elif "summary" in result:
            # 형식 2 처리
            analysis = {
                "summary": result.get("summary", "분석 정보가 없습니다."),
                "content": result.get("main_content", "분석 정보가 없습니다."),
                "impact": {
                    "level": result.get("SK_innovation_impact", {}).get("impact_level", "중간"),
                    "areas": [result.get("SK_innovation_impact", {}).get("impact_area", "정보 없음")],
                    "details": result.get("SK_innovation_impact", {}).get("key_impact_details", ["정보 없음"])
                }
            }
        elif "1. 한 줄 요약" in result:
            # 형식 3 처리 (번호 형식)
            analysis = {
                "summary": result.get("1. 한 줄 요약", "분석 정보가 없습니다."),
                "content": result.get("2. 주요 내용", "분석 정보가 없습니다."),
                "impact": {
                    "level": result.get("3. SK이노베이션 영향", {}).get("영향도", "중간"),
                    "areas": result.get("3. SK이노베이션 영향", {}).get("영향 분야", ["정보 없음"]),
                    "details": result.get("3. SK이노베이션 영향", {}).get("주요 영향 세부 사항", ["정보 없음"])
                }
            }
        else:
            # 기본 형식 (이전 코드)
            analysis = {
                "summary": "분석 정보가 없습니다.",
                "content": "분석 정보가 없습니다.",
                "impact": {
                    "level": "중간",
                    "areas": ["정보 없음"],
                    "details": ["정보 없음"]
                }
            }
            logger.error(f"예상치 못한 API 응답 형식: {result}")
        
        return analysis
        
    except Exception as e:
        logger.error(f"의안 분석 중 오류 발생: {str(e)}")
        # 오류 발생 시 모의 데이터 반환
        return get_mock_analysis(title)

# 실제 의안 데이터 가져오기 함수 정의
def get_real_bills(keywords=None, start_date=None, end_date=None):
    try:
        # BillCrawler 인스턴스 생성
        crawler = BillCrawler()
        
        # 날짜 범위 설정 (기본값: 오늘부터 6일 전까지)
        today = datetime.datetime.now()
        today_str = today.strftime('%Y-%m-%d')
        six_days_ago = today - datetime.timedelta(days=6)
        six_days_ago_str = six_days_ago.strftime('%Y-%m-%d')
        
        # 전달된 날짜 파라미터 사용
        if start_date:
            six_days_ago_str = start_date
        if end_date:
            today_str = end_date
        
        # 키워드가 전달되지 않은 경우 기본값 사용
        if keywords is None:
            keywords = KEYWORDS
        
        # 로그 출력
        logger.info(f"의안 검색 기간: {six_days_ago_str} ~ {today_str}")
        logger.info(f"검색 키워드: {', '.join(keywords)}")
        
        # 날짜 범위와 사용자 지정 키워드로 API 호출하여 의안 정보 가져오기
        bills = crawler.crawl_bills(start_date=six_days_ago_str, end_date=today_str, keywords=keywords)
        
        # 결과 변환 - 앱에서 사용하는 형식으로 변환
        result_bills = []
        for bill in bills:
            result_bills.append({
                "bill_no": bill.get("BILL_NO", ""),
                "title": bill.get("BILL_NAME", ""),
                "proposer": bill.get("PROPOSER", ""),
                "proposal_date": bill.get("PROPOSE_DT", ""),
                "url": bill.get("DETAIL_LINK", ""),
                "keyword": bill.get("keyword", ""),
                "proc_result": bill.get("PROC_RESULT", ""),
                "committee": bill.get("COMMITTEE_NAME", "") or bill.get("COMMITTEE", ""),  # API 필드명 변경 대응
                "committee_review": bill.get("COMMITTEE_REVIEW", ""),
                "committee_id": bill.get("COMMITTEE_ID", ""),  # 추가 필드
                "publ_proposer": bill.get("PUBL_PROPOSER", ""),  # 공동발의자
                "rst_proposer": bill.get("RST_PROPOSER", ""),  # 대표발의자
                "law_proc_dt": bill.get("LAW_PROC_DT", ""),  # 법사위처리일
                "law_present_dt": bill.get("LAW_PRESENT_DT", ""),  # 법사위상정일
                "law_submit_dt": bill.get("LAW_SUBMIT_DT", ""),  # 법사위회부일
                "cmt_proc_result_cd": bill.get("CMT_PROC_RESULT_CD", ""),  # 소관위처리결과
                "cmt_proc_dt": bill.get("CMT_PROC_DT", ""),  # 소관위처리일
                "cmt_present_dt": bill.get("CMT_PRESENT_DT", ""),  # 소관위상정일
                "committee_dt": bill.get("COMMITTEE_DT", ""),  # 소관위회부일
                "proc_dt": bill.get("PROC_DT", ""),  # 의결일
                "law_proc_result_cd": bill.get("LAW_PROC_RESULT_CD", "")  # 법사위처리결과
            })
        
        return result_bills
        
    except Exception as e:
        logger.error(f"의안 정보를 가져오는 중 오류가 발생했습니다: {str(e)}")
        return []

# .env 파일 존재 여부 확인
env_file_exists = pathlib.Path('.env').exists()
if not env_file_exists:
    st.warning("'.env' 파일이 존재하지 않습니다. 프로젝트 루트 디렉토리에 .env 파일을 생성하고 OPENAI_API_KEY를 설정해주세요.")

# OpenAI API 키 설정 (.env 파일에서 가져옴)
if not OPENAI_API_KEY:
    st.error("OpenAI API 키가 설정되지 않았습니다. .env 파일에 OPENAI_API_KEY를 설정해주세요.")
client = OpenAI(api_key=OPENAI_API_KEY)

# 페이지 설정
st.set_page_config(
    page_title="국회 의안정보 크롤러",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 스타일 설정 - 다크 모드 호환성 추가
st.markdown("""
<style>
    /* 다크 모드 대응 색상 변수 */
    :root {
        --text-primary: #1E40AF;
        --text-secondary: #4B5563;
        --background-primary: white;
        --background-secondary: #F9FAFB;
        --border-color: #E5E7EB;
        --accent-color: #DBEAFE;
    }

    /* 다크 모드 대응 */
    @media (prefers-color-scheme: dark) {
        :root {
            --text-primary: #93C5FD;
            --text-secondary: #E5E7EB;
            --background-primary: #1F2937;
            --background-secondary: #111827;
            --border-color: #374151;
            --accent-color: #1E40AF;
        }
        .card {
            background-color: #1F2937 !important;
            border-color: #374151 !important;
        }
        .content-section {
            background-color: #111827 !important;
        }
        p, span, div, h1, h2, h3, h4, h5, h6, li {
            color: #E5E7EB !important;
        }
        a {
            color: #93C5FD !important;
        }
        .card-title {
            color: #93C5FD !important;
            border-bottom-color: #1E40AF !important;
        }
        .section-title {
            color: #93C5FD !important;
            border-left-color: #93C5FD !important;
        }
        strong, b {
            color: #F9FAFB !important;
        }
    }

    /* 전체 스타일 */
    .main-header {color: var(--text-primary); font-size: 2.5rem; font-weight: 700; margin-bottom: 1rem;}
    .sub-header {color: var(--text-secondary); font-size: 1.2rem; margin-bottom: 2rem;}
    
    /* 카드 스타일 개선 */
    .card {
        background-color: var(--background-primary);
        border-radius: 12px;
        padding: 24px;
        margin-bottom: 24px;
        border: 1px solid var(--border-color);
        box-shadow: 0 4px 10px rgba(0, 0, 0, 0.05);
        transition: all 0.2s ease;
    }
    .card:hover {
        box-shadow: 0 8px 15px rgba(0, 0, 0, 0.1);
        transform: translateY(-2px);
    }
    
    /* 카드 제목 스타일 */
    .card-title {
        color: var(--text-primary);
        font-size: 1.5rem;
        font-weight: 600;
        margin-bottom: 1rem;
        border-bottom: 2px solid var(--accent-color);
        padding-bottom: 0.5rem;
    }
    
    /* 섹션 제목 스타일 */
    .section-title {
        color: var(--text-primary);
        font-size: 1.2rem;
        font-weight: 600;
        margin: 15px 0 10px 0;
        border-left: 4px solid var(--text-primary);
        padding-left: 10px;
    }
    
    /* 내용 섹션 스타일 */
    .content-section {
        padding: 15px;
        background-color: var(--background-secondary);
        border-radius: 8px;
        margin-bottom: 15px;
    }
    
    /* 영향도 뱃지 스타일 */
    .impact-badge {
        display: inline-block;
        font-size: 0.75rem;
        padding: 3px 10px;
        border-radius: 20px;
        margin-left: 8px;
        color: white !important;
        font-weight: 600;
    }
    .high {
        background-color: #EF4444;
    }
    .medium {
        background-color: #F59E0B;
    }
    .low {
        background-color: #10B981;
    }
    
    /* 영향도 섹션 스타일 */
    .impact-section {
        margin-top: 15px;
        margin-bottom: 15px;
    }
    .impact-section strong {
        display: block;
        font-weight: 600;
        margin-bottom: 8px;
        color: var(--text-secondary);
    }
    
    /* 버튼 스타일 */
    .stButton > button {
        background-color: var(--text-primary);
        color: white;
        border-radius: 6px;
        padding: 8px 16px;
        border: none;
        transition: all 0.2s ease;
    }
    .stButton > button:hover {
        background-color: #1E3A8A;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    
    /* 구분선 스타일 */
    hr {
        margin: 30px 0;
        border: none;
        height: 1px;
        background-color: var(--border-color);
    }
    
    /* 진행 단계 스타일 */
    .status-badge {
        display: inline-block;
        font-size: 0.75rem;
        padding: 2px 8px;
        border-radius: 4px;
        margin-left: 5px;
        color: white !important;
        font-weight: 600;
    }
    .status-발의 {
        background-color: #3B82F6;
    }
    .status-소관위 {
        background-color: #8B5CF6;
    }
    .status-법사위 {
        background-color: #EC4899;
    }
    .status-본회의 {
        background-color: #F59E0B;
    }
    .status-정부이송 {
        background-color: #10B981;
    }
    .status-공포 {
        background-color: #6B7280;
    }
    
    /* 영향 분야 태그 스타일 */
    .impact-area {
        display: inline-block;
        font-size: 0.7rem;
        padding: 1px 6px;
        border-radius: 4px;
        margin-right: 5px;
        margin-bottom: 5px;
        background-color: #E5E7EB;
        color: #1F2937 !important;
    }
    
    @media (prefers-color-scheme: dark) {
        .impact-area {
            background-color: #374151;
            color: #E5E7EB !important;
        }
    }
    
    .area-지배구조 {
        background-color: #DBEAFE;
        color: #1E40AF !important;
    }
    .area-재무 {
        background-color: #FEF3C7;
        color: #92400E !important;
    }
    .area-인사 {
        background-color: #D1FAE5;
        color: #065F46 !important;
    }
    .area-운영 {
        background-color: #FEE2E2;
        color: #991B1B !important;
    }
    .area-투자 {
        background-color: #E0E7FF;
        color: #3730A3 !important;
    }
    .area-컴플라이언스 {
        background-color: #F5D0FE;
        color: #701A75 !important;
    }
    .area-ESG {
        background-color: #DCFCE7;
        color: #166534 !important;
    }
    
    @media (prefers-color-scheme: dark) {
        .area-지배구조 {
            background-color: #1E40AF;
            color: #DBEAFE !important;
        }
        .area-재무 {
            background-color: #92400E;
            color: #FEF3C7 !important;
        }
        .area-인사 {
            background-color: #065F46;
            color: #D1FAE5 !important;
        }
        .area-운영 {
            background-color: #991B1B;
            color: #FEE2E2 !important;
        }
        .area-투자 {
            background-color: #3730A3;
            color: #E0E7FF !important;
        }
        .area-컴플라이언스 {
            background-color: #701A75;
            color: #F5D0FE !important;
        }
        .area-ESG {
            background-color: #166534;
            color: #DCFCE7 !important;
        }
    }
</style>
""", unsafe_allow_html=True)

# 사이드바 - 검색 조건 표시
st.sidebar.markdown("## 검색 조건")

# 사이드바 설정
st.sidebar.title("설정")

# 키워드 입력 섹션
st.sidebar.markdown("### 검색 키워드")
default_keywords = ["상법", "공정거래"]  # 기본 키워드를 config.py와 일치시킴
user_keywords = []

# 사용자 키워드 입력 UI 추가
keyword_input = st.sidebar.text_input("키워드 입력 (쉼표로 구분)", ", ".join(default_keywords))
if keyword_input:
    user_keywords = [k.strip() for k in keyword_input.split(",") if k.strip()]
    
# 사용할 키워드 결정 (사용자 입력 또는 기본값)
search_keywords = user_keywords if user_keywords else default_keywords
st.sidebar.markdown("**현재 검색 키워드:**")
st.sidebar.markdown("• " + "\n• ".join(search_keywords))

# 날짜 입력 섹션
st.sidebar.markdown("### 검색 날짜")
today = datetime.datetime.now()
six_days_ago = today - datetime.timedelta(days=6)
start_date = st.sidebar.date_input("시작일", six_days_ago)
end_date = st.sidebar.date_input("종료일", today)

# 날짜 검증
if start_date > end_date:
    st.sidebar.error("시작일은 종료일보다 이전이어야 합니다.")
    # 값 재설정
    start_date = six_days_ago
    end_date = today

# 날짜 포맷 변환
start_date_str = start_date.strftime('%Y-%m-%d')
end_date_str = end_date.strftime('%Y-%m-%d')

st.sidebar.markdown(f"**검색 기간:** {start_date_str} ~ {end_date_str}")

# 조회 버튼 추가
search_btn = st.sidebar.button('조회')

# 페이지 제목
st.title("국회 의안 모니터링 시스템")

# 메인 컨텐츠 - 조회 버튼 클릭 시에만 실행
if search_btn:
    with st.spinner("의안정보를 검색 중입니다..."):
        # 실제 크롤러를 사용하여 데이터 가져오기 - 선택한 날짜 범위 적용
        bills = get_real_bills(keywords=search_keywords, start_date=start_date_str, end_date=end_date_str)
        
        if not bills:
            st.warning("검색 결과가 없습니다.")
        
        # 결과 개수 표시
        st.markdown(f"### 총 {len(bills)}개의 의안이 검색되었습니다 (지정한 날짜 범위 내)")
        st.markdown("---")
            
        # 결과 표시 - 카드 형태로 변경
        analyses = []
        for i, bill in enumerate(bills):
            # 법안 내용 분석 결과 가져오기
            analysis = analyze_bill_content(bill['title'], bill['bill_no'], bill['url'])
            analyses.append(analysis)
            
            # 영향도에 따른 클래스 설정
            impact = analysis["impact"]
            badge_class = {
                "높음": "high",
                "중간": "medium",
                "낮음": "low"
            }.get(impact['level'], "medium")
            
            # 심사 진행 단계 배지 클래스 설정
            proc_result = bill.get('proc_result')
            if proc_result is None:
                proc_result = ""
            status_badge_class = get_status_badge_class(proc_result)
            
            # 카드 컨테이너 시작
            st.markdown("<div class='card'>", unsafe_allow_html=True)
            
            # 카드 제목
            st.markdown(f"<div class='card-title'>{bill['title']}</div>", unsafe_allow_html=True)
            
            # 컬럼 레이아웃 생성
            col1, col2 = st.columns([1, 2])
            
            with col1:
                st.markdown("<div class='section-title'>기본 정보</div>", unsafe_allow_html=True)
                
                st.write(f"""
                **의안번호:** {bill.get('bill_no', '정보 없음')}  
                **제안자:** {bill.get('proposer', '정보 없음')}  
                **제안일:** {bill.get('proposal_date', '정보 없음')}  
                **소관위원회:** {bill.get('committee', '정보 없음')}
                """, unsafe_allow_html=True)
                
                if bill.get('url'):
                    st.markdown(f"[상세정보 보기 →]({bill['url']})")
            
            with col2:
                # 한 줄 요약 섹션
                st.markdown("<div class='section-title'>한 줄 요약</div>", unsafe_allow_html=True)
                st.info(analysis['summary'])
                
                # 주요 내용 섹션
                st.markdown("<div class='section-title'>주요 내용</div>", unsafe_allow_html=True)
                content_value = analysis['content']
                if not isinstance(content_value, str):
                    content_value = str(content_value)
                content_lines = content_value.strip().split('\n')
                for line in content_lines:
                    if line.strip():
                        st.write(line.strip())
                
                # --- SK이노베이션 주요 영향 강조 카드 ---
                st.markdown('<hr style="margin:16px 0 8px 0;">', unsafe_allow_html=True)
                st.markdown("<div class='section-title'>SK이노베이션 주요 영향</div>", unsafe_allow_html=True)
                st.markdown('''
                <style>
                .impact-card {
                    background: linear-gradient(90deg, #2563eb 0%, #1e40af 100%);
                    color: #fff !important;
                    border-radius: 12px;
                    box-shadow: 0 4px 16px rgba(30,64,175,0.10);
                    padding: 18px 22px 14px 22px;
                    margin-bottom: 14px;
                    border: 1.5px solid #1e40af;
                    font-size: 1.05rem;
                }
                .impact-card strong {
                    color: #fff !important;
                    font-size: 1.08rem;
                }
                .impact-card .impact-reason {
                    color: #dbeafe !important;
                    font-size: 0.98rem;
                    margin-top: 6px;
                }
                </style>
                ''', unsafe_allow_html=True)
                import ast
                for i, detail in enumerate(impact['details']):
                    parsed_detail = None
                    if isinstance(detail, str):
                        try:
                            if detail.strip().startswith('{') and detail.strip().endswith('}'):
                                parsed_detail = ast.literal_eval(detail)
                        except Exception as e:
                            parsed_detail = None
                    elif isinstance(detail, dict):
                        parsed_detail = detail
                    
                    if isinstance(parsed_detail, dict):
                        content = parsed_detail.get('내용', '')
                        reason = parsed_detail.get('분석 근거', '')
                        st.markdown(f"""
                        <div class='impact-card'>
                            <strong>• {content}</strong>
                            {f'<div class="impact-reason">분석 근거: {reason}</div>' if reason else ''}
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        base_detail = detail.split('(')[0].strip() if isinstance(detail, str) and '(' in detail else detail
                        explanation = ''
                        if isinstance(detail, str) and '(' in detail and ')' in detail:
                            explanation = detail.split('(')[1].split(')')[0]
                        st.markdown(f"""
                        <div class='impact-card'>
                            <strong>• {base_detail}</strong>
                            {f'<div class="impact-reason">분석 근거: {explanation}</div>' if explanation else ''}
                        </div>
                        """, unsafe_allow_html=True)
            
            st.markdown("</div>", unsafe_allow_html=True)

        # --- 이메일 발송 UI 및 로직 추가 ---
        st.markdown("---")
        st.markdown("### 📧 메일로 결과 보내기")
        st.info("아래 버튼을 누르면, 위의 의안 분석 결과가 seungjun@sk.com 으로 메일 발송됩니다.")
        send_btn = st.button("메일로 보내기")
        if send_btn:
            # EmailSender 사용
            from email_sender import EmailSender
            sender = EmailSender()
            # bills와 analyses를 합쳐 템플릿에 맞게 변환
            email_bills = []
            for bill, analysis in zip(bills, analyses):
                email_bills.append({
                    "title": bill.get("title", ""),
                    "proposer": bill.get("proposer", ""),
                    "proposal_date": bill.get("proposal_date", ""),
                    "bill_no": bill.get("bill_no", ""),
                    "summary": analysis.get("summary", ""),
                    "url": bill.get("url", "")
                })
            # 수신자 고정
            sender.recipients = ["seungjun@sk.com"]
            result = sender.send_email(email_bills, search_keywords)
            if result:
                st.success("메일이 성공적으로 seungjun@sk.com 주소로 발송되었습니다!")
            else:
                st.error("메일 발송 중 오류가 발생했습니다. 이메일 설정 또는 네트워크를 확인해주세요.")

# 앱 정보
st.sidebar.markdown("---")
st.sidebar.markdown(f"""
### 앱 정보
**국회 의안정보 크롤러**  
국회 의안정보시스템 API를 활용하여 상법 관련 의안을 검색하고 분석합니다.

### 업데이트 기록
- **2025-06-24**: 사용자 지정 날짜 검색 기능 추가
- **2025-06-23**: 날짜 필터링 기능 강화 (API 결과에서 지정 날짜 범위만 필터링)
- **2025-06-18**: 검색 기간을 7일(오늘부터 6일 전까지)로 확장
- **2025-06-17**: UI/UX 개선, 카드 형태로 변경
- **2025-06-16**: GPT 분석 기능 추가
- **2025-06-15**: 기본 크롤링 기능 구현
""") 

# Streamlit 앱은 자동으로 실행되므로 main() 함수 호출이 필요 없음
if __name__ == "__main__":
    pass 

# 함수가 이미 파일 상단에 정의되어 있으므로 여기서는 제거합니다
