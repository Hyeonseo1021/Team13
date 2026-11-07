# team13 · LNG 탱크 품질검사 교육

신입직원이 LNG 탱크 부품 사진을 보고 직접 양품/불량을 판정한 뒤, AI 검사 모델(분류 ViT · 탐지 EfficientDet · 분할 MaskDINO)의
결과와 비교하며 배우는 Streamlit 웹앱입니다. 오른쪽 **학습 도우미** 채팅창은 AgentStream 챗봇에 연결되어 있습니다.

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

## 학습 도우미 챗봇 연동 구조

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

- 계정, 로그인 세션, AI 판정 검토 기록은 `data/team13.db`(SQLite)에 저장합니다. `data/`는 Git에서 제외됩니다.
- 검토 화면의 **사진 보관 동의**를 켠 경우에만 사진을 저장합니다. 원본 대신 긴 변 1600px JPEG 축소본을 만들고
  EXIF(촬영 기기·위치정보 등)를 지워 `data/photos/<사용자 ID>/<원본 SHA-256>.jpg`에 둡니다(폴더 700, 파일 600).
- 사진은 공개 주소가 없습니다. "내 검토 기록" 화면에서 서버가 로그인한 본인의 사진만 읽어 보여 줍니다.
- 검토일로부터 90일(`PHOTO_DAYS`)이 지난 사진은 기록을 저장하거나 기록 화면을 열 때 자동으로 지웁니다. 텍스트 기록은 남습니다.
- 사용자는 기록 화면의 **내 사진 모두 삭제**로 언제든 자기 사진을 지울 수 있습니다.
