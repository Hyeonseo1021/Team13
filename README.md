# team13 · LNG 탱크 품질검사 교육

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/Hyeonseo1021/Team13)

## Render 무료 배포

현재 앱을 GPU 작업 서버와 별개의 Render 서버에서 실행합니다. `render.yaml`은 **Free** 웹서비스만 생성하며 유료 디스크·DB는 만들지 않습니다.

1. 위 **Deploy to Render** 버튼으로 Render에 로그인하고 GitHub 저장소 접근을 허용합니다. 또는 Render의 **New → Blueprint**에서 이 저장소의 `main`을 선택합니다.
2. 요금제가 **Free**인지 확인합니다. `AGENTSTREAM_API_KEY`에 기존 AgentStream API 키를 입력합니다. 키를 GitHub에 커밋하지 마세요. 키가 없으면 챗봇은 사용할 수 없지만 화면·예제 실습 배포는 가능합니다.
3. **Deploy**를 누릅니다. 빌드·시작이 완료되면 서비스 화면의 `https://<서비스명>.onrender.com/` 주소를 엽니다. 기존 GPU 서버의 `/i/.../` 경로는 붙이지 않습니다.
4. 홈 로고, 검사별 예제 사진, 회원가입·로그인, 이미지 검사, 챗봇을 확인합니다. 이후 `main`에 푸시하면 자동 배포됩니다.

Python 3.12.3과 현재 환경의 패키지 버전을 `Dockerfile`·`requirements.txt`로 고정합니다. `demo_cases/raw/`의 예제 사진과 `assets/`는 이미지에 포함하고, 원본 업로드 임시 폴더 `demo_cases/incoming/`, 개인 데이터 `data/`, 비밀키는 제외합니다. 시작 스크립트는 Render의 `PORT`를 사용하고 기본 경로 `/`에서 실행합니다. 기존 서버의 실행 스크립트는 그대로 유지합니다.

**무료 플랜의 한계**

- 15분 동안 트래픽이 없으면 절전 상태가 되며, 다음 방문 시 재기동 대기 시간이 생깁니다. 무중단 상시 운영을 보장하는 구성은 아닙니다.
- 계정·검토 기록·보관 사진은 로컬 `data/`에 임시 저장됩니다. 재시작·재배포·절전 시 사라질 수 있습니다. 기존 서버의 계정과 사진도 자동 이전되지 않습니다. 영구 보관하려면 외부 DB/파일 저장소 연동 또는 유료 디스크가 필요합니다.
- 무료 메모리 제한 때문에 동시 접속이나 큰 사진 처리 중 종료될 수 있습니다. 예제 파일은 디스크에서 읽으므로 데이터 총용량이 곧 메모리 사용량은 아닙니다. 큰 업로드·동시 사용은 배포 후 별도 확인해야 합니다.
- AI 검사는 외부 `aiopen-serving.jntp-ax.or.kr` API, 챗봇은 AgentStream API가 계속 제공되고 Render에서 접근 가능해야 합니다. 웹앱을 이전하는 것만으로 이 API들의 운영 기간이 연장되지는 않습니다.

공식 안내: [Render 무료 플랜](https://render.com/docs/free), [Docker 배포](https://render.com/docs/docker).

신입직원이 LNG 탱크 부품 사진을 보고 직접 양품/불량을 판정한 뒤, AI 검사 모델(분류 ViT · 탐지 EfficientDet · 분할 MaskDINO)의
결과와 비교하며 배우는 Streamlit 웹앱입니다. 오른쪽 **LNG_NI** 채팅창은 AgentStream 챗봇에 연결되어 있습니다.

## 실행

```bash
pip install streamlit requests pillow numpy pycocotools   # 서버에 이미 설치된 venv: /home/ubuntu/venv
cp .env.example .env                                       # 참고용. 실제 값은 아래 secrets.toml에 넣습니다
mkdir -p .streamlit && $EDITOR .streamlit/secrets.toml     # AGENTSTREAM_API_KEY = "..."
streamlit run app.py --server.baseUrlPath <프록시 경로>
```

- `app.py`: 진입점. `streamlit run`으로 시작하면 `st.App`이 화면(`main.py`)과 챗봇 중계 API(`chat_api.py`)를 함께 띄웁니다.
- `chat_api.py`를 바꾸면 **서버를 재시작**해야 반영됩니다. 화면 코드는 `runOnSave`로 바로 반영됩니다.

### 설정 (환경변수 또는 `.streamlit/secrets.toml`)

| 이름 | 설명 |
|---|---|
| `AGENTSTREAM_API_KEY` | **필수.** 챗봇이 속한 워크스페이스에서 발급한 키. 서버에만 둡니다. |
| `AGENTSTREAM_BASE_URL` | 기본값 `https://api-gateway.jntp-ax.or.kr/agentstream` (`/open/v1`은 코드가 붙임) |
| `AGENTSTREAM_WORKSPACE_ID` / `AGENTSTREAM_CHATBOT_ID` | 연동 대상 UUID (기본값은 `.env.example` 참고) |
| `T13_SESSION_SECRET` | 선택. 방문자 쿠키 서명용 비밀값. 비우면 프로세스마다 새로 만듭니다. |

`.streamlit/secrets.toml`과 `.env`는 `.gitignore`로 Git에서 제외됩니다. Streamlit은 `secrets.toml`의 최상위 값을
환경변수로도 노출하므로 두 곳에 같은 이름을 넣으면 `secrets.toml` 값이 쓰입니다.

## LNG_NI 챗봇 연동 구조

```
브라우저 (assets/site.js)
  └─ POST {baseUrlPath}/api/t13/chat   ← 질문 + 현재 화면의 검사 정보, NDJSON 스트림으로 답변 수신
       우리 서버 (chat_api.py, X-API-Key는 여기서만 붙임)
         ├─ POST /open/v1/chatbots/{챗봇}/sessions          (대화의 첫 질문에서 한 번)
         └─ POST /open/v1/chat-sessions/{session_id}/messages (매 질문, application/x-ndjson)
```

- **시스템 프롬프트는 AgentStream이 적용**합니다. 앱은 `message` 문자열만 보냅니다.
- 질문 앞에 `<inspection_context>` 블록으로 검사 종류 · 내 예상 · 모델 결과를 붙입니다. 정답 라벨은 화면에서 공개된 뒤
  (퀴즈 제출 후)에만 넣고, 사진 파일은 보내지 않습니다. JSON 코드 블록이 아니라 일반 텍스트로 보냅니다
  (AgentStream은 메시지 속 JSON 블록을 분석용 데이터 표로 해석해 거부합니다).
- **세션 격리**: 서버가 HMAC 서명 쿠키로 방문자를 구분하고, `(방문자, 워크스페이스, 챗봇, 대화 ID) → session_id`를
  메모리에 저장합니다. 다른 방문자의 대화 ID로는 접근할 수 없고, 같은 대화는 한 번에 한 질문만 처리합니다.
  서버를 재시작하면 대화 매핑이 사라지며, 브라우저는 새 대화로 다시 시작합니다.
- **스트림 처리**: 바이트를 줄 단위로 나눈 뒤 디코딩해 한글·JSON 줄이 조각나도 복원합니다. `assistant.delta`의 텍스트만
  표시하고(thinking/tool 내용 제외), `event_id` 중복을 버립니다. `turn.completed`만 정상 완료이며 `turn.failed`,
  `tool.failed`, 완료 없는 종료, 잘못된 JSON, 취소, 타임아웃은 받은 답변을 지우지 않고 상태로 표시합니다.
- **근거와 차트**: RAG 결과 문서(`reference`, 본문 조각)를 답변 아래 "참고 문서"로 보여 줍니다. 검색 결과가 0건이면
  그 사실을 표시합니다. `artifact.created`의 visualization 그림은 모두 Plotly(cdnjs 3.0.1)로 그리고,
  manifest의 생성/실패/보류 개수를 함께 표시합니다. 모델이 만든 HTML/JS는 실행하지 않습니다.
- **로그**: 단계 · HTTP 상태 · Content-Type · 경과 시간 · trace/turn ID만 남기고 키와 대화 원문은 남기지 않습니다.
- **상태 확인**: `GET {baseUrlPath}/api/t13/chat/health` (AgentStream health 요약). health가 정상이어도 실제 답변이
  완료되는지는 별도로 확인해야 합니다.

## 테스트

```bash
python -m unittest tests.test_chat_api tests.test_inspection     # 단위 테스트 (네트워크 없음)
python tests/mock_agentstream.py 8598                              # 로컬 대역 AgentStream
AGENTSTREAM_BASE_URL=http://127.0.0.1:8598/agentstream streamlit run app.py --server.port 8599
```

대역 서버는 메시지 속 키워드(SPLIT · FAIL · CUT · BADJSON · CHART · SLOW · HTTP429 · HTML)로 분할 NDJSON, 실패,
완료 없는 종료, 잘못된 JSON, 차트, 취소, 429, HTML 응답을 재현합니다. 대역 응답은 `[대역 응답]`으로 시작하며
실제 챗봇 결과가 아닙니다.

## 데이터

`demo_cases/raw/team13_samples/`의 사진·라벨은 AI Hub "부품 품질 검사 영상 데이터(LNG 탱크)"에서 가져온 표본이며
라이선스는 CC BY-NC-SA(비상업적 이용)입니다. 공개 저장소에 올리기 전에 이용 조건을 확인하세요.

## 계정·검토 기록·사진 보관 (`accounts.py`)

### 검증 사례를 참고하는 챗봇 (`knowledge.py`, `knowledge_ui.py`)

- 판정 검토 시 승인·거절 이유를 기록합니다. 적용 기준은 선택 입력이며, 기존 기록은 마이페이지에서 사유와 기준을 보완할 수 있습니다.
- 마이페이지 → 내 검토 기록에서 행을 선택하고, 텍스트 활용에 별도로 동의한 뒤 **사례 검증 신청**을 누릅니다. 기존 기록은 자동 신청되지 않습니다. 사진 보관·시험 문제 신청과는 별도 동의입니다.
- 관리자 마이페이지의 **챗봇 참고 사례 검증**에서 최종 판정, 확인한 기준·문서 조항, 검증 의견을 입력해 승인합니다. 분야 담당자가 내용을 확인해야 하며, 관리자 승인만으로 전문성이 보장되는 것은 아닙니다.
- **기업 소속 관리**는 관리자만 변경할 수 있습니다. 서버가 로그인 계정의 소속을 조회하여 같은 회사에 공유된 검증 사례만 검색합니다. 소속이 없는 계정의 사례는 본인만 검색하며, 계정을 다른 회사로 옮겨도 기존 사례의 공유 범위는 이동하지 않습니다.
- 질문마다 최근 검증 사례 최대 1,000건에서 검사 종류와 키워드로 관련 사례를 검색하여 최대 3건의 텍스트 요약을 AgentStream에 전달합니다. 모델을 재학습하지 않으며, 사진·파일명·작성자 이름은 참고 사례에 포함하지 않습니다. 검토자가 사유에 직접 적은 민감정보는 사전에 제거해야 합니다.
- 답변에는 `[검토 사례 K번호]`로 근거를 표시하도록 요청하고, 실제로 전달한 사례의 판정·사유·기준·검증 의견을 별도 목록으로 표시합니다. 사례는 과거 기록이며 현재 사진의 정답이나 시각적 근거로 단정하지 않도록 안내합니다.
- 마이페이지에서 **사례 활용 철회**를 누르면 이후 검색에서 제외됩니다. 사유를 수정한 사례도 재신청·재검증이 필요합니다. 계정·회사·사례 상태가 바뀌면 이전 대화를 이어 사용할 수 없도록 분리합니다. 이미 외부 서버에 전송된 대화는 이 기능으로 삭제되지 않습니다.

- 계정, 로그인 세션, AI 판정 검토 기록은 `data/team13.db`(SQLite)에 저장합니다. `data/`는 Git에서 제외됩니다.
- 검토 화면의 **사진 보관 동의**를 켠 경우에만 사진을 저장합니다. 원본 대신 긴 변 1600px JPEG 축소본을 만들고
  EXIF(촬영 기기·위치정보 등)를 지워 `data/photos/<사용자 ID>/<원본 SHA-256>.jpg`에 둡니다(폴더 700, 파일 600).
- 사진은 공개 주소가 없습니다. "내 검토 기록" 화면에서 서버가 로그인한 본인의 사진만 읽어 보여 줍니다.
- 검토일로부터 90일(`PHOTO_DAYS`)이 지난 사진은 기록을 저장하거나 기록 화면을 열 때 자동으로 지웁니다. 텍스트 기록은 남습니다.
- 사용자는 기록 화면의 **내 사진 모두 삭제**로 언제든 자기 사진을 지울 수 있습니다.
