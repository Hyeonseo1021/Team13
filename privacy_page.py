"""?page=privacy · 개인정보 및 데이터 안내, shown as page content (not a pop-up)."""
from ui import shell
from guide_page import note
import accounts


def render():
    days, edge = accounts.PHOTO_DAYS, accounts.PHOTO_EDGE
    sections = [
        ('검사 사진', '검사 실행 시 선택한 사진이 지정된 LNG 탱크 검사 API로 전송됩니다. '
                   '검사 실습에서 올린 사진과 결과는 이 사이트에 저장하지 않습니다.'),
        ('<i class="t13-brand">LNG_NI</i> 챗봇',
         '질문과 현재 화면의 검사 정보(검사 종류·내 예상·모델 결과, 공개된 정답 라벨)를 우리 서버를 거쳐 AgentStream 챗봇 서버로 보냅니다. '
         '사진 파일은 챗봇에 보내지 않습니다. 질문과 답변은 챗봇 서버에 대화 기록으로 저장될 수 있습니다. '
         '브라우저 탭에 보관된 대화는 새 대화 버튼으로 지울 수 있습니다.'),
        ('계정과 검토 기록', '로그인하면 이름과 AI 판정 검토 기록이 이 서버에 저장됩니다. '
                        '비밀번호는 복원할 수 없는 형태(해시)로만 저장합니다.'),
        ('검증 사례 활용', '검토 사유와 검사 기준을 기록한 뒤 별도로 활용에 동의하고 검증을 신청할 수 있습니다. '
                         '관리자가 검증한 텍스트는 소속 회사 사용자(소속이 없으면 본인)의 관련 질문에 참고되며 외부 챗봇 서버로 전송됩니다. '
                         '사진과 파일 이름은 참고 사례에 포함하지 않습니다. 마이페이지에서 활용을 철회하면 이후 검색에서 제외되지만 이미 전송된 대화는 남을 수 있습니다.'),
        ('AI 판정 검토 사진 보관', f'사진 보관에 동의하면 검토한 사진의 축소본(긴 변 {edge}px, 위치정보 등 메타데이터 제거)을 '
                              f'검토일로부터 {days}일간 이 서버에 보관합니다. 공개 주소로 열리지 않으며 로그인한 본인만 '
                              f'"내 검토 기록"에서 볼 수 있고, 같은 화면에서 언제든 모두 지울 수 있습니다. '
                              f'{days}일이 지나면 사진은 자동 삭제되고 검토 기록(텍스트)만 남습니다.'),
    ]
    boxes = ''.join(f'<section class="gd-box"><h3>{t}</h3><p>{d}</p></section>' for t, d in sections)
    html_ = ('<main id="workspace" tabindex="-1" class="guide-main"><div class="breadcrumb">학습 공간 <span aria-hidden="true">/</span> 마이페이지 '
             '<span aria-hidden="true">/</span> 개인정보 및 데이터 안내</div>'
             '<section class="workspace-title"><div class="title-main"><h1>개인정보 및 데이터 안내</h1>'
             '<p>사진·대화·검토 기록이 어디로 보내지고 얼마나 보관되는지 안내합니다.</p></div></section>'
             f'<article class="gd-panel"><div class="gd-grid two">{boxes}</div>'
             + note('회사 보안 규정상 반출이 금지된 현장 사진은 올리지 마세요.') +
             '<p><a class="gd-go" href="?page=my&amp;view=records">내 검토 기록 보기 <span aria-hidden="true">›</span></a></p></article></main>')
    shell(None, no_chat=True, current='my', home=html_)
