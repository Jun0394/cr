import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict, Any
from datetime import datetime
from jinja2 import Template

from config import (
    EMAIL_SENDER, 
    EMAIL_PASSWORD, 
    EMAIL_RECIPIENTS, 
    EMAIL_SUBJECT_PREFIX
)

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 이메일 HTML 템플릿
EMAIL_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 20px; color: #333; }
        .container { max-width: 800px; margin: 0 auto; }
        .header { background-color: #f0f0f0; padding: 10px; border-bottom: 1px solid #ddd; }
        .bill { margin-bottom: 20px; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }
        .bill-title { font-size: 18px; font-weight: bold; margin-bottom: 10px; }
        .bill-info { margin-bottom: 10px; font-size: 14px; color: #666; }
        .bill-summary { line-height: 1.5; }
        .footer { margin-top: 30px; font-size: 12px; color: #999; border-top: 1px solid #ddd; padding-top: 10px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2>국회 의안 정보 알림 ({{ date }})</h2>
            <p>키워드: {{ keywords|join(', ') }}</p>
        </div>
        
        {% if bills %}
            {% for bill in bills %}
            <div class="bill">
                <div class="bill-title">{{ bill.title }}</div>
                <div class="bill-info">
                    <strong>제안자:</strong> {{ bill.proposer }} | 
                    <strong>제안일:</strong> {{ bill.proposal_date }} | 
                    <strong>의안번호:</strong> {{ bill.bill_no }}
                </div>
                <div class="bill-summary">
                    <strong>요약:</strong> {{ bill.summary }}
                </div>
                <div style="margin-top: 10px;">
                    <a href="{{ bill.url }}" target="_blank">상세 정보 보기</a>
                </div>
            </div>
            {% endfor %}
        {% else %}
            <p>오늘 등록된 의안이 없습니다.</p>
        {% endif %}
        
        <div class="footer">
            <p>본 메일은 자동으로 발송되었습니다. 문의사항은 관리자에게 연락해주세요.</p>
        </div>
    </div>
</body>
</html>
"""

class EmailSender:
    """이메일 발송 클래스"""
    
    def __init__(self):
        self.sender = EMAIL_SENDER
        self.password = EMAIL_PASSWORD
        self.recipients = EMAIL_RECIPIENTS
        self.template = Template(EMAIL_TEMPLATE)
    
    def send_email(self, bills: List[Dict[str, Any]], keywords: List[str]) -> bool:
        """의안 정보를 이메일로 발송"""
        try:
            if not self.sender or not self.password or not self.recipients:
                logger.error("이메일 설정이 완료되지 않았습니다.")
                return False
            
            # 이메일 제목 생성
            now = datetime.now()
            time_str = "오전" if now.hour < 12 else "오후"
            subject = f"{EMAIL_SUBJECT_PREFIX} {now.strftime('%Y-%m-%d')} {time_str} 의안 정보"
            
            # 이메일 본문 생성
            html_content = self.template.render(
                bills=bills,
                date=now.strftime("%Y-%m-%d %H:%M"),
                keywords=keywords
            )
            
            # 이메일 메시지 생성
            msg = MIMEMultipart()
            msg['From'] = self.sender
            msg['To'] = ", ".join(self.recipients)
            msg['Subject'] = subject
            
            # HTML 본문 추가
            msg.attach(MIMEText(html_content, 'html'))
            
            # MVP에서는 실제 이메일 발송 대신 로깅만 수행
            logger.info(f"이메일 발송 시뮬레이션: {len(bills)}건의 의안 정보")
            logger.info(f"수신자: {', '.join(self.recipients)}")
            
            # 실제 구현 시 아래 주석 해제
            # SMTP 서버 연결 및 이메일 발송
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                server.login(self.sender, self.password)
                server.send_message(msg)
            
            return True
            
        except Exception as e:
            logger.error(f"이메일 발송 중 오류 발생: {e}")
            return False


if __name__ == "__main__":
    # 테스트
    test_bills = [
        {
            "title": "석유화학산업 진흥에 관한 특별법안",
            "proposer": "홍길동 의원 등 10인",
            "proposal_date": "2023-06-17",
            "bill_no": "2216793",
            "summary": "석유화학산업의 경쟁력 강화와 지속가능한 발전을 위한 법안",
            "url": "https://likms.assembly.go.kr/bill/billDetail.do?billId=2345678"
        }
    ]
    
    sender = EmailSender()
    result = sender.send_email(test_bills, ["석유화학", "배터리", "이차전지", "상법"])
    print(f"이메일 발송 결과: {'성공' if result else '실패'}") 
