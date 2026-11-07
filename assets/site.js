(()=>{
// The assistant lives on <body> (outside Streamlit's scroll area) so it can sit beside the page, not over it.
const mountRoot=document.currentScript.parentElement;const fresh=mountRoot.querySelector('#t13-chat-root');if(!fresh)return;
document.querySelectorAll('body > #t13-chat-root').forEach(x=>x.remove());document.body.appendChild(fresh);
const root=fresh;const $=s=>root.querySelector(s);
const modes={classification:'1. 표면 상태 분류',detection:'2. 볼트·케이블 탐지',segmentation:'3. 결함 영역 분할'};
const dialog=$('#site-dialog');let returnFocus;
function show(title,text){closeAllmenu();if(!dialog.open)returnFocus=document.activeElement;$('#site-dialog-title').textContent=title;$('#site-dialog-copy').textContent=text;dialog.showModal()}
$('#dialog-close').onclick=()=>dialog.close();dialog.addEventListener('close',()=>returnFocus?.focus());
const guide='1. 검사 목적에 맞는 1·2·3 중 하나를 선택합니다.\n2. JPEG 또는 PNG 사진 한 장을 업로드하고, 검사 전 자신의 예상을 기록합니다.\n3. 사진 대상이 일치하는지 확인한 뒤 “선택한 검사 실행”을 누릅니다.\n4. 모델 결과와 원본 사진을 비교하고 추가 확인할 사항을 기록합니다.\n\n모델 점수는 정답률이나 최종 합격 판정을 의미하지 않습니다.';
const topics={photo:['사진 준비 방법','1. JPEG 또는 PNG 사진 한 장을 준비합니다. (10 MiB 이하, 가로×세로 2천만 픽셀 이하)\n2. 검사 종류에 맞는 대상이 사진에 충분히 크게 보이는지 확인합니다.\n   · 표면 상태 분류: 탱크 표면 전체의 클리닝·폼스프레이 상태\n   · 볼트·케이블 탐지: 볼트 체결부와 케이블 설치 부위\n   · 결함 영역 분할: 용접부, 도장면, 보온재 등 결함이 의심되는 부위\n3. 흔들림·역광·심한 반사가 있는 사진은 결과가 불안정할 수 있습니다.\n\n실행하면 사진이 지정된 검사 API로 전송되며, 이 사이트는 사진을 저장하지 않습니다.'],
 result:['결과 해석 방법','· 분류: 사진 전체를 4개 클래스 중 하나로 판정합니다. “해당 없음”이 없어 무관한 사진도 분류됩니다.\n· 탐지: 객체별 클래스·점수·사각형 위치를 보여 줍니다. 아무것도 탐지되지 않았다고 양품이라는 뜻은 아닙니다.\n· 분할: 후보별 픽셀 마스크를 보여 줍니다. 겹치거나 점수가 낮은 후보가 포함될 수 있어, 후보 수가 실제 불량 개수는 아닙니다.\n\n모델 점수는 정답률이나 합격 기준이 아닙니다. 원본 사진과 기업 검사 기준으로 함께 검토하세요.']};
function closeAllmenu(){const m=document.getElementById('t13-allmenu');if(m?.open)m.close()}
const actions={guide:()=>show('실습 이용 가이드',guide),chat:()=>{closeAllmenu();openChat(true)}};
actions.topic=v=>topics[v]&&show(...topics[v]);
actions.classes=v=>{const c=T13_CONTEXT.classes?.[v];if(!c)return;show(c.title+' · 판정 클래스',c.model+' 모델이 구분하는 '+c.classes.length+'개 클래스입니다.\n\n'+c.classes.map((x,i)=>(i+1)+'. '+x).join('\n')+'\n\n해당 검사 페이지에서 사진을 올려 직접 확인해 보세요.')};
actions.company=()=>show('기업교육 안내','기업 신입직원이 LNG 탱크 검사 대상을 이해하고, 직접 관찰한 결과와 AI 분석을 비교하는 학습 공간입니다.\n\n기업별 계정 인증·교육 배정·수료 관리는 추후 연동할 예정입니다. 현재 기업 계정은 시연용이며, 검사 실습은 연결된 실제 API를 사용합니다.');
actions.privacy=()=>show('개인정보 및 데이터 안내','검사 실행 시 선택한 사진이 지정된 LNG 탱크 검사 API로 전송됩니다. 검사 실습에서 올린 사진과 결과는 이 사이트에 저장하지 않습니다.\n\n학습 도우미 챗봇은 질문과 현재 화면의 검사 정보(검사 종류·내 예상·모델 결과, 공개된 정답 라벨)를 우리 서버를 거쳐 AgentStream 챗봇 서버로 보냅니다. 사진 파일은 챗봇에 보내지 않습니다. 질문과 답변은 챗봇 서버에 대화 기록으로 저장될 수 있습니다. 브라우저 탭에 보관된 대화는 새 대화 버튼으로 지울 수 있습니다. 로그인하면 이름과 AI 판정 검토 기록이 이 서버에 저장됩니다. 비밀번호는 복원할 수 없는 형태(해시)로만 저장합니다.\n\nAI 판정 검토에서 사진 보관에 동의하면, 검토한 사진의 축소본(긴 변 1600px, 위치정보 등 메타데이터 제거)을 검토일로부터 90일간 이 서버에 보관합니다. 공개 주소로 열리지 않으며 로그인한 본인만 "내 검토 기록"에서 볼 수 있고, 같은 화면에서 언제든 모두 지울 수 있습니다. 90일이 지나면 사진은 자동 삭제되고 검토 기록(텍스트)만 남습니다.');
actions.account=()=>{show('기업 계정 체험','');$('#site-dialog-copy').innerHTML='<p>실제 인증이 없는 시연 계정입니다. 회사 비밀번호를 입력하지 않습니다.</p><label for="demo-company">소속 기업 (예시)</label><select id="demo-company"><option>제조기업 A</option><option>기술기업 B</option><option>서비스기업 C</option></select><button type="button" class="primary-ui" id="demo-login">시연 계정으로 확인</button>';$('#demo-login').onclick=()=>{const company=$('#demo-company').value;show(company+' · 시연 계정','홈의 1·2·3 버튼으로 검사 교육을 시작할 수 있습니다.\n\n실제 기업 계정·배정 과정·수료 정보는 연결되어 있지 않습니다.')}};
actions.allmenu=()=>{const m=document.getElementById('t13-allmenu');if(m&&!m.open){m.showModal();m.querySelector('.allmenu-close')?.focus()}};
actions.menu=actions.allmenu;
// Buttons live in several st.html blocks: delegate once on document, always calling the latest handlers.
// ---- Accounts: POST {chatApi}/auth/* sets or clears the HttpOnly session cookie; the page then reloads.
const authApi=(T13_CONTEXT.chatApi||'/api/t13')+'/auth/';
function authPost(kind,body){return fetch(authApi+kind,{method:'POST',credentials:'same-origin',headers:{'content-type':'application/json','x-t13-auth':'1'},body:JSON.stringify(body||{})})
  .then(r=>r.json().catch(()=>({})).then(d=>{if(!r.ok)throw new Error(d.message||'요청을 처리하지 못했습니다. 잠시 뒤 다시 시도하세요.');return d}))}
actions.logout=()=>authPost('logout').catch(()=>{}).then(()=>{const q=new URLSearchParams(location.search);location.href=q.get('page')==='login'?location.pathname+'?page=login':location.pathname+location.search});
const loginCard=mountRoot.querySelector('.login-card[data-next]');
if(loginCard){
  const tabs=[...loginCard.querySelectorAll('[role=tab]')];
  function pick(t,focus){tabs.forEach(x=>{const on=x===t;x.setAttribute('aria-selected',String(on));x.tabIndex=on?0:-1;document.getElementById(x.getAttribute('aria-controls')).hidden=!on});
    loginCard.querySelector('#login-title').textContent=t.textContent;if(focus)t.focus();loginCard.querySelector('#'+t.getAttribute('aria-controls')+' input')?.focus()}
  tabs.forEach((t,i)=>{t.onclick=()=>pick(t);t.onkeydown=e=>{if(e.key==='ArrowRight'||e.key==='ArrowLeft'){e.preventDefault();pick(tabs[(i+(e.key==='ArrowRight'?1:tabs.length-1))%tabs.length],true)}}});
  loginCard.querySelectorAll('form').forEach(f=>f.onsubmit=e=>{e.preventDefault();const err=f.querySelector('.login-error'),btn=f.querySelector('.login-submit');
    const name=f.elements.name.value.trim(),pw=f.elements.password.value;err.textContent='';
    if(!name||!pw){err.textContent='이름과 비밀번호를 입력하세요.';(name?f.elements.password:f.elements.name).focus();return}
    if(f.dataset.kind==='signup'&&pw!==f.elements.password2.value){err.textContent='비밀번호 확인이 일치하지 않습니다.';f.elements.password2.focus();return}
    btn.disabled=true;authPost(f.dataset.kind,{name,password:pw}).then(()=>{location.href=location.pathname+(loginCard.dataset.next||'?')})
      .catch(x=>{err.textContent=x.message;btn.disabled=false;f.elements.password.select()})});
  setTimeout(()=>loginCard.querySelector('#li-name')?.focus(),50)}
window.T13_ACTIONS=actions;
const ACTION_NAMES=['guide','company','privacy','account','logout','allmenu','menu','chat','topic','classes'];
if(!window.T13_DELEGATED){window.T13_DELEGATED=true;document.addEventListener('click',e=>{
  if(e.target.closest('[data-allmenu-close]')){closeAllmenu();return}
  if(e.target.closest('.allmenu-link[href]')){closeAllmenu();return}
  const b=e.target.closest(ACTION_NAMES.map(n=>'[data-'+n+']').join(','));if(!b)return;
  const name=ACTION_NAMES.find(n=>b.hasAttribute('data-'+n));e.preventDefault();
  if(name!=='allmenu'&&name!=='menu')closeAllmenu();
  window.T13_ACTIONS?.[name]?.(b.getAttribute('data-'+name))})}
// ---- Learning assistant: AgentStream answers relayed by our own server (POST {chatApi}/chat → NDJSON stream).
// The API key never reaches the browser. State lives on window so a Streamlit re-render, which re-mounts this
// panel, keeps an answer that is still streaming.
const panel=$('#chat-panel'),launcher=$('#chat-launcher'),input=$('#chat-input'),log=$('#chat-log'),sendBtn=$('#chat-send');
const STORE_KEY='team13.learning-chat.v2',API=T13_CONTEXT.chatApi||'api/t13';
const PLOTLY_SRC='https://cdnjs.cloudflare.com/ajax/libs/plotly.js/3.0.1/plotly.min.js';
const GREETING='안녕하세요! team13 학습 도우미입니다.\n\n검사 결과를 보며 궁금한 점, 판정 기준, 관찰 포인트를 물어보세요. 답변은 AI가 생성하며, 지금 화면의 검사 정보(검사 종류·내 예상·모델 결과, 공개된 정답)를 함께 참고합니다.';
const ICON_SEND='<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 20V4m-7 7 7-7 7 7"/></svg>',ICON_STOP='<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><rect x="7" y="7" width="10" height="10" rx="1.5"/></svg>';
class ChatError extends Error{}
const S=window.T13_CHAT||(window.T13_CHAT={messages:null,conv:null,busy:null,open:false,view:null});
if(!S.messages){S.messages=[];
  try{const saved=JSON.parse(sessionStorage.getItem(STORE_KEY)||'{}');
    if(Array.isArray(saved.messages))S.messages=saved.messages.filter(m=>m&&['user','assistant'].includes(m.role)&&typeof m.text==='string').slice(-40);
    if(typeof saved.conv==='string')S.conv=saved.conv;S.open=saved.open===true}catch{}
  S.messages.forEach(m=>{if(m.state==='streaming'){m.state='failed';m.error='페이지를 다시 불러와 답변 수신이 끊겼습니다.'}})}
function persist(){try{sessionStorage.setItem(STORE_KEY,JSON.stringify({conv:S.conv,open:S.open,messages:S.messages.slice(-40).map(m=>{
  if(!m.charts?.length||JSON.stringify(m.charts).length<300000)return m;return {...m,charts:[],chartsDropped:m.charts.length}})}))}catch{}}
// Answers use light markdown: **bold** and pipe tables (header row + |---| line) are rendered, built as DOM nodes (never innerHTML).
// While a table streams in, its header shows as plain text until the separator line arrives.
function fillInline(node,text){String(text).split(/(\*\*[^*\n]+\*\*)/).forEach(part=>{if(/^\*\*[^*\n]+\*\*$/.test(part)){const b=document.createElement('strong');b.textContent=part.slice(2,-2);node.append(b)}else if(part)node.append(document.createTextNode(part))})}
const isTableSep=l=>l.includes('|')&&l.includes('-')&&/^[\s|:-]+$/.test(l);
function tableCells(l){let s=l.trim();if(s.startsWith('|'))s=s.slice(1);if(s.endsWith('|'))s=s.slice(0,-1);return s.split('|').map(c=>c.trim())}
function fillRich(node,text){node.replaceChildren();const lines=String(text).split('\n');let buf=[];
  const flush=()=>{while(buf.length&&!buf[buf.length-1].trim())buf.pop();if(buf.length)fillInline(node,buf.join('\n'));buf=[]};
  for(let i=0;i<lines.length;i++){
    if(!(lines[i].includes('|')&&i+1<lines.length&&isTableSep(lines[i+1]))){if(buf.length||lines[i].trim()||!node.lastChild||node.lastChild.nodeType===3)buf.push(lines[i]);continue}
    flush();const head=tableCells(lines[i]);const wrap=el('div','chat-table-wrap');const t=el('table','chat-table');
    const tr=el('tr');head.forEach(c=>{const th=el('th');fillInline(th,c);tr.append(th)});const thead=el('thead');thead.append(tr);t.append(thead);
    const tbody=el('tbody');i+=2;
    for(;i<lines.length&&lines[i].includes('|')&&lines[i].trim();i++){const cells=tableCells(lines[i]);const r=el('tr');head.forEach((_,k)=>{const td=el('td');fillInline(td,cells[k]??'');r.append(td)});tbody.append(r)}
    i--;t.append(tbody);wrap.append(t);node.append(wrap)}
  flush()}
// AI answers: the first table (key points) and the short explanation under it stay visible. Everything after goes
// under a '분석가이드' heading, one toggle per titled item ('- **다시 볼 점**: …', '**판정 기준**', '### …').
// Open toggles are kept on the message (m.open = {index: true}), so streaming re-renders and reloads keep them open.
function firstTableEnd(lines){for(let i=0;i+1<lines.length;i++)if(lines[i].includes('|')&&isTableSep(lines[i+1])){let j=i+2;while(j<lines.length&&lines[j].includes('|')&&lines[j].trim())j++;return j}return -1}
const GUIDE_HEAD=/^\s*(?:#{1,6}\s+(.+?)|\*\*([^*\n]+?)\*\*\s*[:：]?)\s*$/,GUIDE_ITEM=/^\s*(?:(?:[-*+•]|\d+[.)])\s+\*\*([^*\n]+?)\*\*\s*[:：]?\s*(.*)|\*\*([^*\n]+?)\*\*\s*[:：]\s*(.+))$/;
function guideSections(text){const out=[];let cur=null,gap=false;
  for(const line of text.split('\n')){let g;
    if(!line.trim()){gap=true;if(cur)cur.body.push('');continue}
    if((g=line.match(GUIDE_HEAD))){cur={title:(g[1]||g[2]).trim().replace(/[:：]$/,''),body:[]};out.push(cur)}
    else if((g=line.match(GUIDE_ITEM))){const b=g[2]??g[4];cur={title:(g[1]||g[3]).trim().replace(/[:：]$/,''),body:b?[b]:[]};out.push(cur)}
    else if(!cur||(gap&&!/^\s/.test(line)&&!/^\s*([-*+•]|\d+[.)])\s/.test(line))){cur={title:'',body:[line]};out.push(cur)}
    else cur.body.push(line);
    gap=false}
  return out.map(x=>({title:x.title,body:x.body.join('\n').trim()})).filter(x=>x.body)}
function fillAnswer(node,m){
  if(m.role!=='assistant'||m.kind==='static'){fillRich(node,m.text);return}
  const lines=String(m.text).split('\n');const end=firstTableEnd(lines);
  if(end<0||end>=lines.length){fillRich(node,m.text);return}
  let rest=lines.slice(end).join('\n').trim();fillRich(node,lines.slice(0,end).join('\n'));if(!rest)return;
  // The short explanation right under the table (its first prose paragraph) stays visible.
  const cut=rest.search(/\n\s*\n/);const first=cut<0?rest:rest.slice(0,cut);
  if(!GUIDE_HEAD.test(first.split('\n')[0])&&!GUIDE_ITEM.test(first.split('\n')[0])&&!/^\s*([-*+•#]|\d+[.)]\s)/.test(first)){const brief=el('div','chat-more-body');fillRich(brief,first);node.append(brief);rest=cut<0?'':rest.slice(cut).trim()}
  if(!rest)return;
  const opened=m.open&&typeof m.open==='object'?m.open:{};
  const guide=el('div','chat-guide');const head=el('p','chat-guide-title','분석가이드');if(m.state==='streaming')head.append(el('span','chat-more-live',' · 받는 중…'));guide.append(head);
  guideSections(rest).forEach((sec,i)=>{const body=el('div','chat-more-body');fillRich(body,sec.body);
    if(!sec.title&&sec.body.length<80){body.classList.add('chat-guide-note');guide.append(body);return}
    const box=el('details','chat-more');box.open=!!opened[i];box.append(el('summary','',sec.title||'추가 설명'),body);
    box.addEventListener('toggle',()=>{const o=m.open&&typeof m.open==='object'?m.open:(m.open={});if(!!o[i]!==box.open){if(box.open)o[i]=true;else delete o[i];persist()}});guide.append(box)});
  node.append(guide)}
const el=(tag,cls,text)=>{const e=document.createElement(tag);if(cls)e.className=cls;if(text!=null)e.textContent=text;return e};
function loadPlotly(){if(window.Plotly)return Promise.resolve(window.Plotly);
  if(!window.T13_PLOTLY)window.T13_PLOTLY=new Promise((ok,no)=>{const s=document.createElement('script');s.src=PLOTLY_SRC;s.async=true;s.crossOrigin='anonymous';
    s.onload=()=>window.Plotly?ok(window.Plotly):no(new Error('plotly'));s.onerror=()=>{window.T13_PLOTLY=null;no(new Error('plotly'))};document.head.appendChild(s)});
  return window.T13_PLOTLY}
function drawChart(plot,f){loadPlotly().then(P=>P.newPlot(plot,f.data,{height:300,margin:{l:48,r:16,t:f.layout?.title?40:16,b:44},...f.layout,autosize:true},{responsive:true,displaylogo:false}))
  .catch(()=>plot.replaceWith(el('p','chat-note is-warn','차트 라이브러리를 불러오지 못해 이 차트를 표시할 수 없습니다.')))}
function docLabel(d){const name=d.reference||d.title||d.document_title||d.file_name||d.filename||d.source||d.document_id||d.doc_id||d.id||'문서';const page=d.page??d.page_number;return String(name)+(page!=null&&page!==''?` · p.${page}`:'')}
function sourcesNode(src){
  if(!src.documents.length)return el('p','chat-note','연결된 문서에서 검색된 근거가 없습니다. 이 답변은 문서 근거 없이 작성되었을 수 있습니다.');
  const box=el('details','chat-sources');box.append(el('summary','',`참고 문서 ${src.documents.length}건`));const ol=el('ol');
  src.documents.forEach(d=>{const li=el('li');li.append(el('b','',docLabel(d)));if(d.source_headings)li.append(el('span','',d.source_headings));const snip=d.document||d.content||d.text||d.page_content;if(snip)li.append(el('span','',String(snip).slice(0,180)));ol.append(li)});
  box.append(ol);return box}
function chartNotes(m){const out=[];const mf=m.manifest;
  if(m.charts?.length||mf){let t=`차트 ${m.charts?.length||0}개 표시`;if(mf?.failed_count)t+=` · 생성 실패 ${mf.failed_count}개`;if(mf?.deferred_count)t+=` · 보류 ${mf.deferred_count}개`;out.push(t)}
  if(m.chartInvalid)out.push(`형식 오류로 표시하지 못한 차트 ${m.chartInvalid}개`);
  if(m.chartsDropped)out.push(`차트 ${m.chartsDropped}개는 용량이 커서 새로고침 후 다시 표시되지 않습니다.`);
  if(m.toolFailed?.length)out.push('도구 실행 실패: '+m.toolFailed.join(', '));return out}
function statusNode(m){
  const txt=m.state==='streaming'?(m.phase||'답변 생성 중')+'…':m.state==='done'?'답변 완료':m.state==='cancelled'?'답변을 중지했습니다. 받은 내용까지만 표시합니다.':'⚠ '+(m.error||'답변을 받지 못했습니다.');
  const p=el('p','chat-status',txt);p.dataset.state=m.state||'done';return p}
function renderMessage(m){
  const item=el('div','chat-message'+(m.role==='user'?' user':''));
  item.append(el('p','chat-speaker',m.role==='user'?'나':m.kind==='static'?'team13 학습 도우미 · 기본 안내':'team13 학습 도우미 · AI 답변'));
  const bubble=el('div','chat-bubble'+(m.kind==='static'?' is-static':''));fillAnswer(bubble,m);if(m.role==='assistant'&&m.kind!=='static'&&!m.text)bubble.classList.add('is-empty');item.append(bubble);
  if(m.role==='assistant'&&m.kind!=='static'){
    if(m.charts?.length){const box=el('div','chat-charts');m.charts.forEach((f,i)=>{const fig=el('figure','chat-chart');if(f.title)fig.append(el('figcaption','',f.title));
      const plot=el('div','chat-plot');plot.setAttribute('role','img');plot.setAttribute('aria-label',f.title||`차트 ${i+1}`);fig.append(plot);box.append(fig);drawChart(plot,f)});item.append(box)}
    chartNotes(m).forEach(t=>item.append(el('p','chat-note',t)));
    if(m.sources)item.append(sourcesNode(m.sources));
    item.append(statusNode(m))}
  return item}
const view=()=>S.view||{refresh(){},setBusy(){},paintAll(){}};
function paintAll(){log.replaceChildren(...S.messages.map(renderMessage));log.scrollTop=log.scrollHeight}
function refresh(m,full){const i=S.messages.indexOf(m);if(i<0)return;const node=log.children[i];if(!node){paintAll();return}
  const near=log.scrollHeight-log.scrollTop-log.clientHeight<90;
  if(full)node.replaceWith(renderMessage(m));else{const b=node.querySelector('.chat-bubble');fillAnswer(b,m);b.classList.toggle('is-empty',!m.text);node.querySelector('.chat-status')?.replaceWith(statusNode(m))}
  if(near)log.scrollTop=log.scrollHeight}
function setBusy(b){sendBtn.classList.toggle('is-stop',b);sendBtn.innerHTML=b?ICON_STOP:ICON_SEND;sendBtn.setAttribute('aria-label',b?'답변 생성 중지':'메시지 보내기');
  sendBtn.disabled=b?false:!input.value.trim();root.querySelectorAll('[data-prompt]').forEach(x=>x.disabled=b)}
S.view={refresh,setBusy,paintAll};
function add(m){S.messages.push(m);if(S.messages.length>40){S.messages=S.messages.slice(-40)}persist();paintAll()}
function handle(m,ev){
  switch(ev.t){
    case 'meta':if(typeof ev.conversation_id==='string')S.conv=ev.conversation_id;persist();return;
    case 'status':m.phase=String(ev.phase||'');view().refresh(m);return;
    case 'delta':m.text+=typeof ev.text==='string'?ev.text:'';view().refresh(m);return;
    case 'sources':m.sources={documents:Array.isArray(ev.documents)?ev.documents:[],queries:ev.queries||[]};break;
    case 'chart':{(m.charts||(m.charts=[])).push(...(Array.isArray(ev.figures)?ev.figures:[]));const mf=ev.manifest||{},cur=m.manifest||(m.manifest={});
      ['generated_count','failed_count','deferred_count'].forEach(k=>{if(Number.isInteger(mf[k]))cur[k]=(cur[k]||0)+mf[k]});m.chartInvalid=(m.chartInvalid||0)+(ev.invalid||0);break}
    case 'tool_failed':(m.toolFailed||(m.toolFailed=[])).push(ev.name||'도구');break;
    case 'done':if(m.state==='streaming')m.state='done';break;
    case 'error':m.state='failed';m.error=ev.message||'오류가 발생했습니다.';if(ev.reset)S.conv=null;break;
    default:return}
  persist();view().refresh(m,true)}
async function send(text){
  text=text.trim();if(!text||S.busy)return;
  const context=window.T13_INSPECTION_CONTEXT??null;
  const m={role:'assistant',kind:'ai',text:'',state:'streaming',phase:'연결 중'};
  add({role:'user',text});add(m);input.value='';
  const ctrl=new AbortController();S.busy={ctrl,m};view().setBusy(true);
  const timer=setTimeout(()=>ctrl.abort('timeout'),330000);
  try{
    const res=await fetch(API+'/chat',{method:'POST',credentials:'same-origin',signal:ctrl.signal,
      headers:{'Content-Type':'application/json','X-T13-Chat':'1'},body:JSON.stringify({conversation_id:S.conv,message:text,context})});
    const ct=res.headers.get('content-type')||'';
    if(!res.ok||!ct.includes('application/x-ndjson')){let msg=`우리 서버 응답 오류 (HTTP ${res.status})`;
      if(ct.includes('application/json')){const j=await res.json().catch(()=>null);if(j?.message)msg=j.message;if(j?.reset)S.conv=null}
      else if(ct.includes('text/html'))msg+=' · JSON 대신 웹페이지가 왔습니다. 서버가 아직 챗봇 연동 모드로 재시작되지 않았거나 프록시 오류일 수 있습니다.';
      throw new ChatError(msg)}
    const reader=res.body.getReader(),dec=new TextDecoder('utf-8');let buf='';
    const take=line=>{line=line.trim();if(!line)return;let ev;try{ev=JSON.parse(line)}catch{throw new ChatError('응답 형식 오류로 수신을 멈췄습니다. 받은 내용까지만 표시합니다.')}handle(m,ev)};
    for(;;){const {value,done}=await reader.read();if(done)break;buf+=dec.decode(value,{stream:true});let nl;while((nl=buf.indexOf('\n'))>=0){take(buf.slice(0,nl));buf=buf.slice(nl+1)}}
    buf+=dec.decode();take(buf);
    if(m.state==='streaming')throw new ChatError('답변이 완료 신호 없이 끝났습니다. 받은 내용까지만 표시합니다.');
  }catch(e){
    if(m.state==='streaming'){
      if(ctrl.signal.aborted){if(ctrl.signal.reason==='timeout'){m.state='failed';m.error='응답 시간이 너무 길어 중단했습니다. 잠시 후 다시 시도해 주세요.'}else m.state='cancelled'}
      else{m.state='failed';m.error=e instanceof ChatError?e.message:'우리 서버에 연결하지 못했습니다. 네트워크 상태를 확인해 주세요.'}}
  }finally{clearTimeout(timer);S.busy=null;persist();view().refresh(m,true);view().setBusy(false)}}
function reset(){if(S.busy)S.busy.ctrl.abort();const old=S.conv;S.conv=null;
  if(old)fetch(API+'/chat/reset',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-T13-Chat':'1'},body:JSON.stringify({conversation_id:old})}).catch(()=>{});
  S.messages=[{role:'assistant',kind:'static',text:GREETING}];persist();paintAll();input.value='';setBusy(false)}
// Inspection pages open the assistant only from the button beside “검사 실행”; no floating launcher there.
function openChat(open,focus=true){S.open=open;panel.hidden=!open;document.body.classList.toggle('t13-chat-open',open);launcher.hidden=open||!!T13_CONTEXT.mode||!!T13_CONTEXT.noChat;launcher.setAttribute('aria-expanded',String(open));persist();if(focus)(open?input:(T13_CONTEXT.mode?document.querySelector('.run-chat-btn'):launcher))?.focus();log.scrollTop=log.scrollHeight}
if(!S.messages.length)S.messages=[{role:'assistant',kind:'static',text:GREETING}];
paintAll();setBusy(!!S.busy);if(T13_CONTEXT.noChat){panel.hidden=true;launcher.hidden=true;document.body.classList.remove('t13-chat-open')}else openChat(S.open,false);
if(T13_CONTEXT.mode)$('#chat-context-label').textContent='현재 실습 · '+modes[T13_CONTEXT.mode];
launcher.onclick=()=>openChat(true);$('#chat-close').onclick=()=>openChat(false);$('#chat-reset').onclick=()=>{reset();input.focus()};panel.addEventListener('keydown',e=>{if(e.key==='Escape'){e.preventDefault();e.stopPropagation();openChat(false)}});
input.addEventListener('input',()=>{if(!S.busy)sendBtn.disabled=!input.value.trim()});input.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing&&e.keyCode!==229){e.preventDefault();if(!S.busy)send(input.value)}});$('#chat-form').onsubmit=e=>{e.preventDefault();if(S.busy)S.busy.ctrl.abort();else send(input.value)};root.querySelectorAll('[data-prompt]').forEach(b=>b.onclick=()=>send(b.dataset.prompt));
// ---- GNB mega menu: hover (mouse), click/Enter (touch, keyboard), Escape and arrow keys.
const gnbItems=[...mountRoot.querySelectorAll('.gnb-item')];const canHover=matchMedia('(hover:hover)');
function setOpen(li,open){li.classList.toggle('open',open);li.querySelector('.gnb-btn').setAttribute('aria-expanded',String(open))}
function closeGnb(except){gnbItems.forEach(li=>li!==except&&setOpen(li,false))}
gnbItems.forEach((li,idx)=>{const btn=li.querySelector('.gnb-btn');
  li.addEventListener('mouseenter',()=>{if(canHover.matches){closeGnb(li);setOpen(li,true);li.dataset.via='hover'}});
  li.addEventListener('mouseleave',()=>{if(canHover.matches&&!li.contains(document.activeElement))setOpen(li,false)});
  btn.addEventListener('click',()=>{if(li.dataset.via==='hover'&&li.classList.contains('open')){li.dataset.via='click';return}li.dataset.via='click';const o=!li.classList.contains('open');closeGnb(li);setOpen(li,o)});
  li.addEventListener('focusout',e=>{if(!li.contains(e.relatedTarget))setOpen(li,false)});
  li.addEventListener('keydown',e=>{
    if(e.key==='Escape'&&li.classList.contains('open')){e.preventDefault();setOpen(li,false);btn.focus();return}
    const links=[...li.querySelectorAll('.mega-link')];const at=links.indexOf(document.activeElement);
    if(e.target===btn&&e.key==='ArrowDown'){e.preventDefault();closeGnb(li);setOpen(li,true);links[0]?.focus()}
    else if(at>=0&&(e.key==='ArrowDown'||e.key==='ArrowUp')){e.preventDefault();links[(at+(e.key==='ArrowDown'?1:-1)+links.length)%links.length].focus()}
    else if(e.target===btn&&(e.key==='ArrowRight'||e.key==='ArrowLeft')){e.preventDefault();gnbItems[(idx+(e.key==='ArrowRight'?1:-1)+gnbItems.length)%gnbItems.length].querySelector('.gnb-btn').focus()}})});

// ---- Integrated search (combobox + listbox) over pages, guide topics and judgement classes.
const sForm=mountRoot.querySelector('#t13-search'),sInput=mountRoot.querySelector('#t13-q'),sList=mountRoot.querySelector('#t13-search-list');
const sToggle=mountRoot.querySelector('.search-toggle'),sHeader=mountRoot.querySelector('.site-header');
if(sToggle)sToggle.onclick=()=>{const open=!sHeader.classList.contains('search-open');sHeader.classList.toggle('search-open',open);sToggle.setAttribute('aria-expanded',String(open));sToggle.setAttribute('aria-label',open?'통합검색 닫기':'통합검색 열기');if(open)mountRoot.querySelector('#t13-q')?.focus()};
if(sForm){let results=[],active=-1;const norm=s=>s.toLowerCase().replace(/[\s·.]/g,'');
  function closeList(){sList.hidden=true;sInput.setAttribute('aria-expanded','false');sInput.removeAttribute('aria-activedescendant');active=-1}
  function paintList(empty){sList.replaceChildren();
    if(empty){const li=document.createElement('li');li.className='search-empty';li.setAttribute('role','option');li.setAttribute('aria-disabled','true');li.textContent='“'+sInput.value.trim()+'”에 대한 검색 결과가 없습니다.';sList.append(li)}
    results.forEach((x,i)=>{const li=document.createElement('li');li.id='t13-opt-'+i;li.setAttribute('role','option');li.setAttribute('aria-selected',String(i===active));
      const t=document.createElement('strong');t.textContent=x.t;const s=document.createElement('span');s.textContent=x.s;li.append(t,s);
      li.addEventListener('mousedown',e=>{e.preventDefault();choose(i)});sList.append(li)});
    sList.hidden=!(results.length||empty);sInput.setAttribute('aria-expanded',String(!sList.hidden));
    if(active>=0)sInput.setAttribute('aria-activedescendant','t13-opt-'+active);else sInput.removeAttribute('aria-activedescendant')}
  function find(){const v=norm(sInput.value);const seen=new Set();results=v?(T13_CONTEXT.search||[]).filter(x=>norm(x.t+x.q).includes(v)&&!seen.has(x.t+x.v)&&seen.add(x.t+x.v)).slice(0,8):[];active=-1;paintList(false)}
  function choose(i){const x=results[i];if(!x)return;closeList();sInput.blur();if(x.k==='href')location.href=x.v;else window.T13_ACTIONS?.[x.k]?.(x.v)}
  sInput.addEventListener('input',find);
  sInput.addEventListener('keydown',e=>{if(e.isComposing)return;
    if(e.key==='ArrowDown'||e.key==='ArrowUp'){if(!results.length)return;e.preventDefault();active=(active+(e.key==='ArrowDown'?1:-1)+results.length)%results.length;paintList(false);document.getElementById('t13-opt-'+active)?.scrollIntoView({block:'nearest'})}
    else if(e.key==='Escape'){if(!sList.hidden){e.preventDefault();closeList()}else sInput.value=''}});
  sForm.addEventListener('submit',e=>{e.preventDefault();if(!sInput.value.trim())return sInput.focus();if(!results.length)find();if(results.length)choose(active>=0?active:0);else paintList(true)});
  sForm.addEventListener('focusout',e=>{if(!sForm.contains(e.relatedTarget))closeList()})}

// ---- Hero slider: manual only (‹ ›), so no auto-advance and no pause control is needed (WCAG 2.2.2).
const slider=mountRoot.querySelector('.hero-slider');
if(slider){const slides=[...slider.querySelectorAll('.slide')],track=slider.querySelector('.slides');let cur=0;clearInterval(window.T13_SLIDE_TIMER);
  track.setAttribute('aria-live','polite');
  function go(n){cur=(n+slides.length)%slides.length;slides.forEach((s,k)=>{s.hidden=k!==cur});slider.querySelector('.slide-current').textContent=cur+1}
  slider.querySelector('.slide-prev').onclick=()=>go(cur-1);slider.querySelector('.slide-next').onclick=()=>go(cur+1);
  go(0)}
})();
