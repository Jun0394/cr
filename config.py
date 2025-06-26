import os
# .env 파일 로드 부분 제거
# load_dotenv()

# OpenAI API 설정 - 직접 키 입력
OPENAI_API_KEY = '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'

# 이메일 설정 - 실제 발신자 정보 입력
EMAIL_SENDER = 'lsj6248@gmail.com'
EMAIL_PASSWORD = 'docl xkgr potm sifx'
EMAIL_RECIPIENTS = []  # 수신자는 앱에서 입력받음

# 키워드 필터링
KEYWORDS = ['상법', '공정거래']  # 직접 키워드 설정

# 크롤링 설정
ASSEMBLY_URL = "https://open.assembly.go.kr/portal/openapi/nzmimeepazxkubdpn"  # 국회 의안정보시스템 Open API URL
CRAWL_INTERVAL_MORNING = "07:30"  # KST
CRAWL_INTERVAL_AFTERNOON = "14:30"  # KST

# 이메일 발송 설정
EMAIL_SEND_MORNING = "08:30"  # KST
EMAIL_SEND_AFTERNOON = "15:00"  # KST

# 이메일 템플릿 설정
EMAIL_SUBJECT_PREFIX = "[국회 의안 알림]" 
