// ═══ GTPlayer Editor — Preview-Based Inline Editor (v3) ═══

const COLORS = ['#10b981','#6366f1','#f59e0b','#ef4444','#8b5cf6','#ec4899','#14b8a6','#f97316','#06b6d4','#84cc16'];
const TAG_PRESETS = [
  {tag:'출시',bg:'#dcfce7',c:'#15803d'},{tag:'업데이트',bg:'#dbeafe',c:'#1e40af'},{tag:'할인',bg:'#fee2e2',c:'#b91c1c'},
  {tag:'인사이동',bg:'#fef9c3',c:'#854d0e'},{tag:'펀딩',bg:'#ede9fe',c:'#6d28d9'},{tag:'이슈',bg:'#fce7f3',c:'#be185d'},
  {tag:'인수합병',bg:'#ccfbf1',c:'#0f766e'},{tag:'법률',bg:'#f3f4f6',c:'#374151'}
];
const P_COLORS = {PC:['#dbeafe','#1d4ed8'],PS5:['#ede9fe','#6d28d9'],Xbox:['#ede9fe','#6d28d9'],Mobile:['#dcfce7','#15803d'],Switch:['#fee2e2','#b91c1c']};

// ── Static i18n templates (no API cost) ──
const I18N = {
  ko: {
    headerSub: 'DAILY GAME INTELLIGENCE',
    edition: num => `에디션 #${num}`,
    readTime: '⏱ 3분',
    footerTag: '게임 산업 인사이트, 매일 아침 7시',
    sections: {
      calendar: '📅 PC·콘솔·모바일 신작 게임 출시일정',
      calendarEvents: '🏆 글로벌 게임쇼 및 e스포츠 대회 일정',
      briefing: '📰 게임 산업 비즈니스 및 최신 이슈 브리핑',
      feedback: '💬 글로벌 최신 게임 유저 반응 및 리뷰 분석',
      drk: '✍️ 게임 트렌드 및 마켓 인사이트 분석',
      gamescene: '🎬 오늘의 게임 컨셉 아트 갤러리',
      meme: '🔥 이번 주 해외 게임 커뮤니티 화제의 밈',
      soundtrack: '🎧 명작 게임 OST 플레이리스트 추천',
      trailer: '🍿 기대작 게임 플레이 영상 및 트레일러',
      epic: '🎮 스팀 할인 및 에픽게임즈 무료 배포 혜택',
      chart: '📊 오늘 주목받는 스팀·모바일 게임 인기 순위',
      newsletter_feedback: '🙏 뉴스레터 피드백',
      poll: '🗳️ 설문 / 투표'
    },
    chartCols: ['🖥 PC TOP 3', '🎮 콘솔 TOP 3', '📱 모바일 TOP 3'],
    tags: {
      '출시':'출시','업데이트':'업데이트','할인':'할인','이슈':'이슈',
      '인사이동':'인사이동','펀딩':'펀딩','인수합병':'인수합병','법률':'법률',
      '행사':'행사','대회':'대회','발표':'발표','쇼케이스':'쇼케이스'
    },
    misc: { community: '커뮤니티' },
    score: '종합 점수', pos: '긍정적', neu: '중립', neg: '부정적',
    collected: '수집', unit: '건', insight: '✍️ 게임에 대한 인사이트',
    addRelease: '+ 출시 게임 추가', addEvent: '+ 이벤트 추가',
    addBriefing: '+ 뉴스 추가', addComment: '+ 코멘트 추가',
    nlQuestion: '오늘 소식은 어땠나요?', nlUp: '👍 도움돼요', nlDown: '👎 그저 그래요',
    youtubeListen: 'YouTube에서 듣기', youtubeWatch: 'YouTube에서 시청',
    epicGet: '무료로 받기'
  },
  en: {
    headerSub: 'DAILY GAME INTELLIGENCE',
    edition: num => `Edition #${num}`,
    readTime: '⏱ 3 min',
    footerTag: 'Game Industry Insight, Every Morning at 7 AM',
    sections: {
      calendar: '📅 Upcoming PC, Console & Mobile Game Releases',
      calendarEvents: '🏆 Global Gaming Events & Esports Schedule',
      briefing: '📰 Global Gaming Industry News & Business Updates',
      feedback: '💬 Global Player Reviews & Feedback Analysis',
      drk: '✍️ Gaming Industry Trends & Market Insights',
      gamescene: "🎬 Today's Game Concept Art Gallery",
      meme: '🔥 Trending Memes in Global Gaming Communities',
      soundtrack: '🎧 Recommended Masterpiece Game OST Playlists',
      trailer: '🍿 Highly Anticipated Game Gameplay & Trailers',
      epic: '🎮 Steam Sales & Free Epic Games Deals',
      chart: '📊 Trending Steam & Mobile Game Rankings Today',
      newsletter_feedback: '🙏 Newsletter Feedback',
      poll: '🗳️ Poll'
    },
    chartCols: ['🖥 PC TOP 3', '🎮 Console TOP 3', '📱 Mobile TOP 3'],
    tags: {
      '출시':'Release','업데이트':'Update','할인':'Sale','이슈':'Issue',
      '인사이동':'Personnel','펀딩':'Funding','인수합병':'M&A','법률':'Legal',
      '행사':'Event','대회':'Tournament','발표':'Announce','쇼케이스':'Showcase'
    },
    misc: { community: 'Community' },
    score: 'Score', pos: 'Positive', neu: 'Neutral', neg: 'Negative',
    collected: 'Collected', unit: '', insight: '✍️ Game Insight',
    addRelease: '+ Add Game', addEvent: '+ Add Event',
    addBriefing: '+ Add News', addComment: '+ Add Comment',
    nlQuestion: 'How was today\'s briefing?', nlUp: '👍 Helpful', nlDown: '👎 Not great',
    youtubeListen: 'Listen on YouTube', youtubeWatch: 'Watch on YouTube',
    epicGet: 'Get it Free'
  },
  ja: {
    headerSub: 'DAILY GAME INTELLIGENCE',
    edition: num => `エディション #${num}`,
    readTime: '⏱ 3分',
    footerTag: 'ゲーム業界インサイト、毎朝7時配信',
    sections: {
      calendar: '📅 PC・スマホ・家庭用ゲーム新作発売カレンダー',
      calendarEvents: '🏆 グローバルゲームショウ＆eスポーツ日程',
      briefing: '📰 グローバルゲーム業界の最新ニュース・トレンド',
      feedback: '💬 最新ゲームのグローバルユーザー反響＆レビュー分析',
      drk: '✍️ ゲーム市場の変化を読む専門インサイト',
      gamescene: '🎬 本日のゲームコンセプトアートギャラリー',
      meme: '🔥 今週の海外ゲームコミュニティ話題のミーム',
      soundtrack: '🎧 名作ゲームOSTプレイリストおすすめ',
      trailer: '🍿 期待作のゲームプレイ映像＆トレーラー',
      epic: '🎮 Steamセール・Epic無料配布ゲーム情報',
      chart: '📊 今日注目のSteam・モバイルゲーム人気ランキング',
      newsletter_feedback: '🙏 ニュースレターフィードバック',
      poll: '🗳️ アンケート'
    },
    chartCols: ['🖥 PC TOP 3', '🎮 コンソール TOP 3', '📱 モバイル TOP 3'],
    tags: {
      '출시':'リリース','업데이트':'アップデート','할인':'セール','이슈':'イシュー',
      '인사이동':'人事','펀딩':'ファンディング','인수합병':'M&A','법률':'法律',
      '행사':'イベント','대회':'大会','발표':'発表','쇼케이스':'ショーケース'
    },
    misc: { community: 'コミュニティ' },
    score: '総合スコア', pos: 'ポジティブ', neu: 'ニュートラル', neg: 'ネガティブ',
    collected: '収集', unit: '件', insight: '✍️ ゲームインサイト',
    addRelease: '+ ゲーム追加', addEvent: '+ イベント追加',
    addBriefing: '+ ニュース追加', addComment: '+ コメント追加',
    nlQuestion: '今日のニュースはいかがでしたか？', nlUp: '👍 役に立った', nlDown: '👎 いまいち',
    youtubeListen: 'YouTubeで聴く', youtubeWatch: 'YouTubeで視聴',
    epicGet: '無料で入手'
  }
};
function t(key){ return (I18N[curLang]||I18N.ko)[key] || (I18N.ko)[key] || key; }
function ts(secKey){ return ((I18N[curLang]||I18N.ko).sections||{})[secKey] || ((I18N.ko).sections||{})[secKey] || secKey; }
function tTag(koTag){ return ((I18N[curLang]||I18N.ko).tags||{})[koTag] || koTag; }

// ── XSS 방지: HTML 이스케이프 ──
function escapeHtml(str) {
  if (typeof str !== 'string') return str;
  // Decode existing basic HTML entities first to avoid double-escaping
  const unescaped = str
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&amp;/g, '&');
  return unescaped
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}
function sanitizeStrings(obj) {
  if (typeof obj === 'string') return escapeHtml(obj);
  if (Array.isArray(obj)) return obj.map(sanitizeStrings);
  if (obj && typeof obj === 'object') {
    const out = {};
    for (const [k, v] of Object.entries(obj)) out[k] = sanitizeStrings(v);
    return out;
  }
  return obj;
}

function makeSample(num) {
  const d = new Date().toISOString().slice(0,10);
  return {
    num, date:d, status:'draft',
    schedule:{date:'',time:'07:00',target:'all',languages:['ko','en']},
    sections:{
      calendar:{enabled:true,
        releases:[
          {game:'Elden Ring: Nightreign',dev:'FromSoftware',date:'3월 16일(일)',platforms:['PC','PS5','Xbox'],color:'#10b981',note:''},
          {game:'Blue Protocol: Resonance',dev:'Bandai Namco',date:'3월 18일(화)',platforms:['Mobile','PC'],color:'#6366f1',note:'글로벌 동시 출시'},
          {game:'Final Fantasy XVII',dev:'Square Enix',date:'3월 20일(목)',platforms:['PC','PS5'],color:'#f59e0b',note:'얼리 액세스'}
        ],
        events:[{name:'G-Star 2026',note:'개최 확정',venue:'부산 BEXCO',date:'11월 13~16일',tag:'KR 이벤트'}]
      },
      briefing:{enabled:true,
        items:[
          {tag:'출시',tagBg:'#dcfce7',tagColor:'#15803d',title:'G-Star 2026, 부산 벡스코 11월 개최 공식 확정 — 역대 최대 규모',source:'인벤',time:'2시간 전'},
          {tag:'업데이트',tagBg:'#dbeafe',tagColor:'#1e40af',title:'League of Legends 2026 시즌 개편 — 랭크 시스템 전면 재설계',source:'게임메카',time:'4시간 전'},
          {tag:'할인',tagBg:'#fee2e2',tagColor:'#b91c1c',title:'Steam 스프링 세일 시작 — 인기 타이틀 최대 90% 할인',source:'Steam',time:'오늘~3/21'},
          {tag:'인사이동',tagBg:'#fef9c3',tagColor:'#854d0e',title:'Hideo Kojima, Sony 공동 투자로 VOID Productions 설립',source:'Polygon',time:'6시간 전'},
          {tag:'펀딩',tagBg:'#ede9fe',tagColor:'#6d28d9',title:'크래프톤, 인도 모바일 스튜디오에 300억 원 투자 확정',source:'파이낸셜뉴스',time:'8시간 전'}
        ]
      },
      feedback:{enabled:false,
        items:[
          {
            game:'Elden Ring: Nightreign',period:'출시 1주차',count:'12,847',sources:'인벤, Steam, Reddit',
            score:'4.2',pos:74,neu:16,neg:10,
            keywords:[
              {text:'🎯 전투 시스템 혁신',positive:true},{text:'🌍 오픈월드 방대함',positive:true},
              {text:'✨ 그래픽 최고 수준',positive:true},{text:'⚠ 초반 최적화 이슈',positive:false},
              {text:'🐛 로딩 시간 급등',positive:false}
            ],
            comments:[
              {text:'역대 FromSoftware 최고작. 멀티플레이 협동이 완전히 새로운 장을 열었다.',meta:'Steam · 87시간 · 추천',positive:true},
              {text:'보스전에서 RTX 4090도 60fps 불안. 최적화 패치 필요.',meta:'Reddit r/eldenring · 비추천',positive:false}
            ]
          }
        ]
      },
      drk:{enabled:true,
        title:'AI가 게임 개발의 문을 열고 있다 — 기회인가, 위기인가?',
        intro:'이번 주 넥슨이 AI 스튜디오를 공개하면서, 업계의 논쟁이 수면 위로 올라왔습니다. AI가 NPC 대화를 쓰고 배경 아트를 생성하는 시대. 이것은 단순한 위기보다 창의의 혁명이라고 봅니다.',
        points:'① 예전엔 AAA 스튜디오만 할 수 있던 것을 인디 개발자 혼자서도 가능하게 됩니다.\n\n② AI가 못하는 것: 플레이어가 왜 감동받는지. 데이터는 무엇을 알려주지만 왜는 사람의 영역.\n\n③ 살아남는 게임사는 AI를 두려워하는 곳이 아니라 AI를 가장 잘 다루는 곳.'
      },
      gamescene:{enabled:true,game:'Elden Ring: Nightreign',title:'무너져가는 세계의 끝자락에 서다.',imgUrl:'assets/gamescene_001.png',comment:'FromSoftware는 언제나 씬 하나로 모든 것을 말한다.'},
      meme:{enabled:false,items:[]},
      soundtrack:{enabled:false,title:'',channel:'',videoId:'',url:'',thumbnail:'',comment:''},
      chart:{enabled:true,
        pc:[{game:'Elden Ring DLC',change:'▲NEW'},{game:'Path of Exile 2',change:''},{game:'Counter-Strike 2',change:''}],
        console:[{game:'Final Fantasy XVII',change:''},{game:'God of War: Myth',change:''},{game:'Spider-Man 3',change:''}],
        mobile:[{game:'Blue Protocol',change:'▲NEW'},{game:'Genshin Impact',change:''},{game:'Honor of Kings',change:''}]
      },
      newsletter_feedback:{enabled:true,
        question:'',
        upLabel:'', downLabel:'',
        upLink:'https://forms.gle/up', downLink:'https://forms.gle/down'
      },
      poll:{enabled:false,
        question:'가장 기대되는 2026년 기대작은?',
        options:[
          {text:'Monster Hunter Wilds',link:'https://poll.game/1'},
          {text:'GTA VI',link:'https://poll.game/2'},
          {text:'Crimson Desert',link:'https://poll.game/3'}
        ]
      }
    },
    translations:{en:{},ja:{}}
  };
}

// ── STATE ──
const K = 'gt_editions_v3';
let editions = JSON.parse(localStorage.getItem(K)||'[]');
let curIdx = 0, curLang = 'ko';
let dragState = null; // {sec, arr, from}

// ── UNDO / REDO STACK ──
const undoStack = [];
const redoStack = [];
const MAX_HISTORY = 20;
let lastSavedJson = '';
function pushUndo(){
  if(!editions.length || curIdx < 0) return;
  const snap = JSON.stringify(editions[curIdx]);
  if(snap === lastSavedJson) return; // no change
  undoStack.push(lastSavedJson);
  if(undoStack.length > MAX_HISTORY) undoStack.shift();
  redoStack.length = 0; // clear redo on new change
  lastSavedJson = snap;
}
function initUndoState(){
  if(editions.length && curIdx >= 0){
    lastSavedJson = JSON.stringify(editions[curIdx]);
  }
}
function undo(){
  if(!undoStack.length){ toast('⚠️ 되돌릴 내역이 없습니다'); return; }
  redoStack.push(JSON.stringify(editions[curIdx]));
  editions[curIdx] = JSON.parse(undoStack.pop());
  lastSavedJson = JSON.stringify(editions[curIdx]);
  localStorage.setItem(K, JSON.stringify(editions));
  render();
  toast('↩️ 되돌리기 완료');
}
function redo(){
  if(!redoStack.length){ toast('⚠️ 다시 실행할 내역이 없습니다'); return; }
  undoStack.push(JSON.stringify(editions[curIdx]));
  editions[curIdx] = JSON.parse(redoStack.pop());
  lastSavedJson = JSON.stringify(editions[curIdx]);
  localStorage.setItem(K, JSON.stringify(editions));
  render();
  toast('↪️ 다시 실행 완료');
}
// Ctrl+Z / Ctrl+Y handler
document.addEventListener('keydown', e => {
  if(!e.target.isContentEditable && (e.ctrlKey || e.metaKey)){
    if(e.key === 'z'){ e.preventDefault(); undo(); }
    if(e.key === 'y'){ e.preventDefault(); redo(); }
  }
});

function save(skipUndo){ if(!skipUndo) pushUndo(); localStorage.setItem(K, JSON.stringify(editions)); }
function cur(){ return editions[curIdx]; }
function randColor(){ return COLORS[Math.floor(Math.random()*COLORS.length)]; }

// ── SAVE ON BLUR (replaces collectEditable) ──
function onCEBlur(el){
  const sec = el.dataset.sec, field = el.dataset.field;
  let val = el.innerText.trim();
  // 감성 바 필드(pos, neu, neg)는 숫자만 추출하고 re-render
  const barFields = ['pos','neu','neg'];
  const lastKey = field.split('.').pop();
  if(sec==='feedback' && barFields.includes(lastKey)){
    val = parseInt(val.replace(/[^0-9]/g,''),10)||0;
  }
  if(curLang==='ko'){
    setNested(cur().sections[sec], field, val);
  } else {
    if(!cur().translations[curLang]) cur().translations[curLang]={};
    if(!cur().translations[curLang][sec]) cur().translations[curLang][sec]={};
    cur().translations[curLang][sec][field] = val;
  }
  save();
  // 감성 바 필드 수정 시 바 업데이트를 위해 re-render
  if(sec==='feedback' && barFields.includes(lastKey)){
    render();
  }
}
function setNested(obj, path, val){
  const keys = path.split('.');
  let o = obj;
  for(let i=0;i<keys.length-1;i++){
    const k = keys[i]; if(o[k]===undefined) o[k]={};
    o = o[k];
  }
  o[keys[keys.length-1]] = val;
}
function getTrans(sec, field){
  if(curLang==='ko') return null;
  const t = cur().translations[curLang];
  if(!t||!t[sec]) return null;
  return t[sec][field] ?? null;
}
function tv(sec,field,orig){ const t=getTrans(sec,field); return escapeHtml((t&&t.trim()!=='')?t:orig); }
function ceAttr(sec,field){ return `contenteditable="true" data-sec="${sec}" data-field="${field}" onblur="onCEBlur(this)"`; }

// ── UTILS ──
function isPastScheduled(e) {
  if (e.status === 'published') return true;
  if (!e.schedule || !e.schedule.date) return false;
  const t = e.schedule.time || '07:00';
  const dt = new Date(`${e.schedule.date}T${t}:00`);
  return new Date() > dt;
}

// ── INIT ──
function init(){
  editions = editions.filter(e => !isPastScheduled(e));
  if(!editions.length) editions.push(makeSample('001'));
  save(true); renderSidebar(); loadEdition(0);
  initUndoState();
  // Sync published status from server
  syncPublished();
}
function syncPublished(){
  fetch('/api/published').then(r=>r.json()).then(res=>{
    if(!res.published||!res.published.length) return;
    const before = editions.length;
    editions = editions.filter(e => !res.published.includes(e.num) && !isPastScheduled(e));
    if(editions.length < before){
      if(!editions.length) editions.push(makeSample(String(parseInt(res.published[res.published.length-1])+1).padStart(3,'0')));
      curIdx = 0; save(); renderSidebar(); loadEdition(0);
      toast(`📤 ${before - editions.length}개 에디션 발행 완료 → 삭제됨`);
    }
  }).catch(()=>{});
}

// ── SIDEBAR ──
function toggleSidebar(){
  document.getElementById('sidebar').classList.toggle('open');
  document.getElementById('sidebarOverlay').classList.toggle('open');
}
function renderSidebar(){
  const m={draft:'초안',scheduled:'예약됨'};
  document.getElementById('editionList').innerHTML = editions.map((e,i)=>
    `<li class="ed-item${i===curIdx?' active':''}" style="display:flex;align-items:center;gap:6px">
      <div style="flex:1;cursor:pointer" onclick="loadEdition(${i});toggleSidebar()">
        <span class="ed-num">#${e.num}</span><span class="ed-date">${e.date}</span>
        <span class="ed-badge ed-badge-${e.status}">${m[e.status]||e.status}</span>
      </div>
      <button onclick="event.stopPropagation();deleteEdition(${i})" style="background:none;border:none;color:#ef4444;cursor:pointer;font-size:10px;padding:6px 10px;opacity:0.7;z-index:5;flex-shrink:0" onmouseover="this.style.opacity=1" onmouseout="this.style.opacity=0.7" title="삭제">✕</button>
    </li>`
  ).join('');
}
function deleteEdition(idx){
  const targetNum = editions[idx].num;
  if(!confirm(`에디션 #${targetNum}을 삭제하시겠습니까?`)) return;
  editions.splice(idx, 1);
  
  fetch('/api/delete-edition', {
    method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({num: targetNum})
  }).catch(e => console.error(e));

  if(!editions.length){
    curIdx = -1;
    save(); renderSidebar(); renderEmptyState();
    toast('🗑️ 모든 에디션이 화면에서 숨겨지고 예약이 해제되었습니다');
    return;
  }
  if(curIdx >= editions.length) curIdx = editions.length - 1;
  save(); renderSidebar(); loadEdition(curIdx);
  toast('🗑️ 화면에서 지워지고 해당 에디션의 예약이 취소되었습니다 (파일은 보존됨)');
}
function renderEmptyState(){
  document.getElementById('editionLabel').textContent = '에디션 없음';
  document.getElementById('schedBanner').style.display='none';
  document.getElementById('newsletterWrap').innerHTML = `<div style="text-align:center;padding:80px 20px;color:#9ca3af">
    <div style="font-size:48px;margin-bottom:16px">📂</div>
    <div style="font-size:10px;font-weight:600;margin-bottom:8px">에디션이 없습니다</div>
    <div style="font-size:13px">사이드바에서 JSON 파일을 불러와 시작하세요</div></div>`;
}
function loadEdition(idx){
  curIdx=idx; curLang='ko';
  document.querySelectorAll('.lang-btn').forEach(b=>b.classList.toggle('active',b.textContent.includes('KR')));
  document.getElementById('editionLabel').textContent=`에디션 #${cur().num} · ${cur().date}`;
  updateSchedBanner(); renderSidebar(); render();
  initUndoState();
}

// ── SCHEDULE BANNER ──
function updateSchedBanner(){
  const b=document.getElementById('schedBanner'), bt=document.getElementById('schedBannerText');
  if(cur().status==='scheduled'&&cur().schedule.date){
    b.style.display=''; bt.textContent=`📅 ${cur().schedule.date} ${cur().schedule.time} 발송 예약됨`;
  } else { b.style.display='none'; }
}

// ── LANGUAGE ──
function switchLang(lang,btn){
  curLang=lang;
  document.querySelectorAll('.lang-btn').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active'); render();
}
async function autoTranslate(){
  if(!editions.length || curIdx < 0){ toast('⚠️ 에디션이 없습니다'); return; }
  
  const btn = document.querySelector('.lang-auto-btn');
  const oldText = btn.innerHTML;
  btn.innerHTML = '⏳ 번역 진행 중...';
  btn.disabled = true;
  btn.style.opacity = '0.7';
  btn.style.cursor = 'wait';
  
  toast('🤖 번역 중... (10~20초 소요)');
  try {
    const payload = cur();
    payload.keepExisting = document.getElementById('keepExistingTranslations').checked;
    const resp = await fetch('/api/translate', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify(payload)
    });
    const res = await resp.json();
    if(res.ok){
      cur().translations = res.translations;
      save(); render();
      toast('✅ 영어/일본어 번역 완료!');
    } else {
      toast('❌ 번역 실패: ' + (res.error||''));
    }
  } catch(e){
    toast('❌ 서버 연결 실패: ' + e.message);
  } finally {
    btn.innerHTML = oldText;
    btn.disabled = false;
    btn.style.opacity = '1';
    btn.style.cursor = 'pointer';
  }
}

// ── RENDER ──
function ensureSectionDefaults(s){
  // Ensure all section keys exist with at least {enabled:false} to prevent crashes
  const defaults = {
    calendar:{enabled:true,releases:[],events:[]},
    briefing:{enabled:true,items:[]},
    feedback:{enabled:true,game:'',period:'',count:'0',sources:'',score:'0',pos:0,neu:0,neg:0,keywords:[],comments:[]},
    drk:{enabled:true,title:'',intro:'',points:''},
    gamescene:{enabled:false,game:'',title:'',imgUrl:'',comment:''},
    meme:{enabled:false,title:'',url:'',what_happened:'',one_liner:'',preview_img:'',score:0,subreddit:'',permalink:''},
    soundtrack:{enabled:false,title:'',channel:'',videoId:'',url:'',thumbnail:'',comment:''},
    trailer:{enabled:false,title:'',channel:'',videoId:'',url:'',thumbnail:'',comment:''},
    epic:{enabled:false,title:'',url:'',thumbnail:'',comment:''},
    chart:{enabled:false,pc:[],console:[],mobile:[]},
    newsletter_feedback:{enabled:true,question:'',upLabel:'',downLabel:''},
    poll:{enabled:false,question:'',options:[]}
  };
  for(const [k,v] of Object.entries(defaults)){
    if(!s[k]) s[k] = v;
  }
}
function render(){
  const s=cur().sections;
  ensureSectionDefaults(s);
  const wrap=document.getElementById('newsletterWrap');
  let h=renderHeader();
  const secs=[
    {key:'calendar',num:'01',label:ts('calendar'),fn:renderCalendar},
    {key:'briefing',num:'02',label:ts('briefing'),fn:renderBriefing},
    {key:'feedback',num:'03',label:ts('feedback'),fn:renderFeedback},
    {key:'drk',num:'04',label:ts('drk'),fn:renderDrK},
    {key:'gamescene',num:'05',label:ts('gamescene'),fn:renderGamescene},
    {key:'meme',num:'05b',label:ts('meme'),fn:renderMeme},
    {key:'soundtrack',num:'05c',label:ts('soundtrack'),fn:renderSoundtrack},
    {key:'trailer',num:'05d',label:ts('trailer'),fn:renderTrailer},
    {key:'epic',num:'05e',label:ts('epic'),fn:renderEpic},
    {key:'chart',num:'06',label:ts('chart'),fn:renderChart},
    {key:'newsletter_feedback',num:'07',label:ts('newsletter_feedback'),fn:renderNewsletterFeedback},
    {key:'poll',num:'08',label:ts('poll'),fn:renderPoll}
  ];
  secs.forEach(sec=>{
    const en=s[sec.key].enabled;
    h+=`<div class="sec-wrap${en?'':' disabled'}">
      <div class="sec-ctrl"><label class="toggle"><input type="checkbox" ${en?'checked':''} onchange="toggleSection('${sec.key}',this.checked)"><span class="toggle-track"></span><span class="toggle-thumb"></span></label>
      <span class="sec-ctrl-label">${sec.label}</span>
      <button class="ctrl-btn" onclick="regenerate('${sec.key}')">🔄 재생성</button></div>
      <div class="sec-content" id="content-${sec.key}">${sec.fn(s[sec.key],sec.key)}</div></div>`;
  });
  wrap.innerHTML=h;
}

function renderHeader(){
  const langLabel={ko:'KO',en:'EN',ja:'JP'};
  const langBadge=l=>`<span style="background:${curLang===l?'#000':'#fff'};color:${curLang===l?'#fff':'#888'};font-size:11px;font-weight:800;padding:8px 12px;margin-left:4px;${curLang!==l?'border:1px solid #e5e7eb;':''}">${langLabel[l]||l.toUpperCase()}</span>`;
  return `<div style="background:#fff;padding:4px 44px 20px"><div style="display:flex;justify-content:space-between;align-items:center">
    <div style="font-size:18px;font-weight:900;letter-spacing:1px;color:#000;text-transform:uppercase">${t('headerSub')}</div>
    <div style="display:flex">${langBadge('ko')}${langBadge('en')}${langBadge('ja')}</div></div></div><div style="background:#000;height:4px;margin:0 44px"></div>`;
}

// ── DRAG & DROP ──
function onDragStart(sec,arr,idx,e){ dragState={sec,arr,from:idx}; e.dataTransfer.effectAllowed='move'; e.target.style.opacity='.4'; }
function onDragEnd(e){ e.target.style.opacity='1'; dragState=null; }
function onDragOver(e){ e.preventDefault(); e.dataTransfer.dropEffect='move'; }
function onDrop(sec,arr,toIdx,e){
  e.preventDefault();
  if(!dragState||dragState.sec!==sec||dragState.arr!==arr) return;
  const list=cur().sections[sec][arr], item=list.splice(dragState.from,1)[0];
  list.splice(toIdx,0,item); save(); render();
}

// ── SECTION RENDERERS ──
function renderCalendar(d,key){
  let h=`<div style="background:#fff;padding:36px 44px 28px">
    <div style="font-size:22px;font-weight:900;color:#000;margin-bottom:20px;padding-bottom:14px;border-bottom:1px solid #e0e0e0">${ts('calendar')}</div>`;
  d.releases.forEach((r,i)=>{
        const platText = (r.platforms||[]).join(', ');
    // Parse date like "3월 20일(목)" → "3/20" and "목"
    const rawDate = r.date || '';
    let dTop = rawDate, dBot = '';
    const dm = rawDate.match(/(\d+)월\s*(\d+)일/);
    if(dm){ dTop = dm[1]+'/'+dm[2]; }
    const daym = rawDate.match(/\(([^)]+)\)/);
    if(daym){ 
      const tD = daym[1];
      const dow = {en:{'월':'Mon','화':'Tue','수':'Wed','목':'Thu','금':'Fri','토':'Sat','일':'Sun'}, ja:{'월':'月','화':'火','수':'水','목':'木','금':'金','토':'土','일':'日'}}[curLang];
      dBot = dow ? (dow[tD] || tD) : tD;
    }
    h+=`<div class="item-row" draggable="true" ondragstart="onDragStart('calendar','releases',${i},event)" ondragend="onDragEnd(event)" ondragover="onDragOver(event)" ondrop="onDrop('calendar','releases',${i},event)"
      style="background:#f9fafb;margin-bottom:6px;display:flex;align-items:stretch;cursor:grab;border:1px solid #e5e7eb">
      <div style="background:#1f2937;color:#fff;min-width:56px;max-width:56px;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:8px 4px;flex-shrink:0">
        <div style="font-size:14px;font-weight:800;line-height:1">${dTop}</div>
        <div style="font-size:10px;font-weight:500;color:#9ca3af;margin-top:2px">${dBot}</div>
        <input type="hidden" data-sec="calendar" data-field="releases.${i}.date" value="${rawDate}">
      </div>
      <div style="flex:1;padding:10px 14px;display:flex;align-items:center;gap:10px">
        <div style="flex:1">
          <div style="font-size:14px;font-weight:700;color:#111827;line-height:1.3">
            <span ${ceAttr(key,'releases.'+i+'.game')}>${tv(key,'releases.'+i+'.game',r.game)}</span>${r.article_url?' <span style="cursor:default">&nearr;</span>':''}
            <span style="font-size:11px;font-weight:400;color:#9ca3af;margin-left:6px" ${ceAttr(key,'releases.'+i+'.dev')}>${tv(key,'releases.'+i+'.dev',r.dev)}</span></div>
          ${platText ? `<div style="font-size:10px;color:#9ca3af;margin-top:3px">${platText}</div>` : ''}
          ${r.note ? `<div style="font-size:11px;color:#9ca3af;margin-top:2px" ${ceAttr(key,'releases.'+i+'.note')}>${tv(key,'releases.'+i+'.note',r.note)}</div>` : ''}
        </div>
        
      </div>
      <button class="btn-del-item" style="position:static;transform:none;border-left:1px solid #e5e7eb;border-radius:0;padding:0 12px;margin:0" onclick="delItem('calendar','releases',${i})">✕</button></div>`;
  });
  h+=`<button class="btn-add-item" onclick="addRelease()">+ 출시 게임 추가</button>`;
  h+=`<div style="font-size:11px;font-weight:700;color:#9ca3af;text-transform:uppercase;letter-spacing:2px;margin:20px 0 12px">${ts('calendarEvents')}</div>`;
  d.events.forEach((ev,i)=>{
    h+=`<div class="item-row" draggable="true" ondragstart="onDragStart('calendar','events',${i},event)" ondragend="onDragEnd(event)" ondragover="onDragOver(event)" ondrop="onDrop('calendar','events',${i},event)"
      style="background:#fff7ed;padding:14px 18px;border-left:2px solid #000;display:flex;justify-content:space-between;align-items:center;cursor:grab">
      <div style="flex:1"><div style="font-size:14px;font-weight:700;color:#111827">
        <span ${ceAttr(key,'events.'+i+'.name')}>${tv(key,'events.'+i+'.name',ev.name)}</span>
        <span style="font-size:11px;font-weight:400;color:#9ca3af;margin-left:4px" ${ceAttr(key,'events.'+i+'.note')}>${tv(key,'events.'+i+'.note',ev.note)}</span></div>
        <div style="font-size:11px;color:#9ca3af;margin-top:2px">
          <span ${ceAttr(key,'events.'+i+'.venue')}>${tv(key,'events.'+i+'.venue',ev.venue)}</span> · <span ${ceAttr(key,'events.'+i+'.date')}>${tv(key,'events.'+i+'.date',(ev.date||'').replace(/~/g,' ~ ').replace(/  ~/g,' ~').replace(/~  /g,'~ '))}</span></div></div>
      <span style="background:#f0f0f0;color:#000;font-size:10px;font-weight:600;padding:3px 8px" ${ceAttr(key,'events.'+i+'.tag')}>${tTag(tv(key,'events.'+i+'.tag',ev.tag))}</span>
      <button class="btn-del-item" onclick="delItem('calendar','events',${i})">✕</button></div>`;
  });
  h+=`<button class="btn-add-item" onclick="addEvent()">+ 이벤트 추가</button>`;
  return h+'</div>';
}

function renderBriefing(d,key){
  let h=`<div style="background:#fff;padding:28px 44px;border-top:1px solid #e0e0e0">
    <div style="font-size:22px;font-weight:900;color:#000;margin-bottom:20px;padding-bottom:14px;border-bottom:1px solid #e0e0e0">${ts('briefing')}</div>`;
  d.items.forEach((item,i)=>{
        const tp = TAG_PRESETS.find(t=>t.tag===item.tag);
    const tBg = item.tagBg || (tp?tp.bg:'#e5e7eb');
    const tColor = item.tagColor || (tp?tp.c:'#374151');
    const tagDisplay = tTag(item.tag);
    h+=`<div class="item-row" draggable="true" ondragstart="onDragStart('briefing','items',${i},event)" ondragend="onDragEnd(event)" ondragover="onDragOver(event)" ondrop="onDrop('briefing','items',${i},event)"
      style="margin-bottom:14px;border-bottom:1px solid #e5e7eb;padding-bottom:14px;display:flex;gap:12px;align-items:flex-start;cursor:grab">
      <span style="background:${tBg};color:${tColor};font-size:9px;font-weight:700;padding:3px 0;width:56px;text-align:center;box-sizing:border-box;white-space:nowrap;flex-shrink:0;margin-top:3px;cursor:pointer" onclick="cycleBriefingTag(${i})" title="클릭하여 태그 변경">${tagDisplay}</span>
      <div style="flex:1"><div style="font-size:14px;font-weight:600;color:#111827;line-height:1.4"><span ${ceAttr(key,'items.'+i+'.title')}>${tv(key,'items.'+i+'.title',item.title)}</span>${item.article_url?' <span style="cursor:default">&nearr;</span>':''}</div>
      <div style="font-size:11px;color:#9ca3af;margin-top:4px"><span ${ceAttr(key,'items.'+i+'.source')}>${tv(key,'items.'+i+'.source',item.source)}</span> · <span ${ceAttr(key,'items.'+i+'.time')}>${tv(key,'items.'+i+'.time',item.time==='오늘'?cur().date:(item.time||cur().date))}</span></div></div>
      <button class="btn-del-item" style="position:static;transform:none;flex-shrink:0" onclick="delItem('briefing','items',${i})">✕</button></div>`;
  });
  h+=`<button class="btn-add-item" onclick="addBriefing()">+ 뉴스 추가</button>`;
  return h+'</div>';
}

function renderFeedback(d,key){
  let items = d.items || [d];
  let h = `<div style="background:#fff;padding:28px 44px">
    <div style="font-size:22px;font-weight:900;color:#000;margin-bottom:4px;padding-bottom:14px;border-bottom:1px solid #e0e0e0">${ts('feedback')}</div>`;
  items.forEach((item, idx) => {
    const prefix = d.items ? `items.${idx}.` : '';
    h += `<div style="${idx>0?'border-top:1px dashed #e5e7eb;padding-top:20px;margin-top:20px':''}">
      ${d.items ? `<button class="btn-del-item" style="float:right" onclick="delItem('feedback','items',${idx})">✕</button>` : ''}
      <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-top:10px">
        <div><div style="font-size:17px;font-weight:800;color:#111827" ${ceAttr(key,prefix+'game')}>${tv(key,prefix+'game',item.game)}</div>
          <div style="font-size:11px;color:#9ca3af;margin-top:2px">
            <span ${ceAttr(key,prefix+'period')}>${tv(key,prefix+'period',item.period)}</span> · ${t('collected')} <span ${ceAttr(key,prefix+'count')}>${tv(key,prefix+'count',item.count)}</span>${curLang==='en'?'':t('unit')} (<span ${ceAttr(key,prefix+'sources')}>${curLang==='ko'?tv(key,prefix+'sources',item.sources):((I18N[curLang]||{}).misc||{}).community||item.sources}</span>)</div></div>
        <div style="background:#fafafa;border:1px solid #e0e0e0;padding:8px 16px;text-align:center">
          <div style="font-size:9px;color:#000;font-weight:700;letter-spacing:1px">${t('score')}</div>
          <div style="font-size:24px;font-weight:900;color:#000;line-height:1.1" ${ceAttr(key,prefix+'score')}>${tv(key,prefix+'score',item.score)}</div>
          <div style="font-size:10px;color:#6b7280">/5.0</div></div></div>`;
    
    const bars=[[t('pos'),'pos','#10b981'],[t('neu'),'neu','#f59e0b'],[t('neg'),'neg','#ef4444']];
    h+='<div style="margin:18px 0">';
    bars.forEach(([l,k,c])=>{
      h+=`<div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">
        <span style="font-size:11px;color:#374151;min-width:80px">${l}</span>
        <div style="flex:1;background:#e5e7eb;height:9px"><div style="background:${c};width:${item[k]}%;height:9px"></div></div>
        <span style="font-size:12px;font-weight:800;color:${c};min-width:32px;text-align:right" ${ceAttr(key,prefix+k)}>${item[k]}%</span></div>`;
    });
    h+='</div><div class="tag-wrap" style="margin-bottom:16px">';
    item.keywords.forEach((kw,i)=>{
      const bg=kw.positive?'#dcfce7':'#fee2e2', c=kw.positive?'#15803d':'#b91c1c';
      h+=`<span class="tag-item" style="display:inline-block;background:${bg};color:${c};font-size:11px;font-weight:600;padding:4px 10px;margin:2px;cursor:pointer" onclick="toggleKwSentiment(${idx},${i})" title="클릭: 긍정/부정 전환">
        <span ${ceAttr(key,prefix+'keywords.'+i+'.text')}>${tv(key,prefix+'keywords.'+i+'.text',kw.text)}</span>
        <span class="tag-x" onclick="event.stopPropagation();delKeyword(${idx},${i})">✕</span></span>`;
    });
    h+=`<button class="btn-add-tag" onclick="addKeyword(${idx})">+ 키워드</button></div>`;
    item.comments.forEach((c,i)=>{
      h+=`<div class="item-row" style="background:#f9fafb;padding:16px 18px;border-left:2px solid ${c.positive?'#10b981':'#ef4444'};margin-bottom:8px">
        <div style="font-size:13px;color:#374151;line-height:1.6" ${ceAttr(key,prefix+'comments.'+i+'.text')}>"${tv(key,prefix+'comments.'+i+'.text',c.text)}"</div>
        ${c.meta ? `<div style="font-size:10px;color:#9ca3af;margin-top:6px" ${ceAttr(key,prefix+'comments.'+i+'.meta')}>${tv(key,prefix+'comments.'+i+'.meta',c.meta)}</div>` : ''}
        <button class="btn-del-item" onclick="delFeedbackComment(${idx},${i})">✕</button></div>`;
    });
    h+=`<button class="btn-add-item" onclick="addFeedbackComment(${idx})">+ 코멘트 추가</button></div>`;
  });
  if(d.items) h+=`<button class="btn-add-item" style="border-style:solid;border-color:#10b981;color:#10b981;margin-top:12px" onclick="addFeedbackItem()">+ 게임 피드백 추가</button>`;
  return h+'</div>';
}


function renderNewsletterFeedback(d,key){
  return `<div style="background:#fafafa;padding:28px 16px;text-align:center;border-top:1px solid #e0e0e0">
    <div style="font-size:14px;font-weight:700;color:#111827;margin-bottom:16px" ${ceAttr(key, 'question')}>${tv(key, 'question', d.question||t('nlQuestion'))}</div>
    <div style="display:flex;justify-content:center;gap:12px">
      <div style="flex:1;background:#fff;border:1px solid #e0e0e0;padding:12px;font-weight:600" ${ceAttr(key, 'upLabel')}>${tv(key, 'upLabel', d.upLabel||t('nlUp'))}</div>
      <div style="flex:1;background:#fff;border:1px solid #e0e0e0;padding:12px;font-weight:600" ${ceAttr(key, 'downLabel')}>${tv(key, 'downLabel', d.downLabel||t('nlDown'))}</div>
    </div>
  </div>`;
}

function renderPoll(d,key){
  let h = `<div style="background:#fff;padding:28px 44px;border-top:1px solid #e0e0e0">
    <div style="font-size:22px;font-weight:900;color:#000;margin-bottom:16px;padding-bottom:14px;border-bottom:1px solid #e0e0e0" ${ceAttr(key,'question')}>${tv(key,'question',d.question)}</div>`;
  d.options.forEach((opt, i) => {
    h += `<div class="item-row" style="background:#f9fafb;padding:14px 18px;margin-bottom:8px;border:1px solid #e0e0e0">
      <div style="font-size:13px;font-weight:700;color:#000" ${ceAttr(key,'options.'+i+'.text')}>${tv(key,'options.'+i+'.text',opt.text)}</div>
      <div style="font-size:10px;color:#9ca3af;margin-top:2px;word-break:break-all" ${ceAttr(key,'options.'+i+'.link')}>${opt.link}</div>
      <button class="btn-del-item" onclick="delItem('poll','options',${i})">✕</button></div>`;
  });
  h += `<button class="btn-add-item" onclick="addPollOption()">+ 설문 항목 추가</button></div>`;
  return h;
}

function mdBold(str){
  // Convert **text** to <strong>text</strong>
  if(typeof str !== 'string') return str;
  return str.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
}
function renderDrK(d,key){
  return `<div style="background:#fafafa;padding:28px 44px;border-top:2px solid #e0e0e0">
    <div style="font-size:22px;font-weight:900;color:#000;margin-bottom:20px;padding-bottom:14px;border-bottom:1px solid #e0e0e0">${ts('drk')}</div>
    <div style="font-size:15px;font-weight:700;color:#111827;margin-bottom:12px" ${ceAttr(key,'title')}>${tv(key,'title',d.title)}</div>
    <div style="font-size:13px;color:#374151;line-height:1.9;margin-bottom:16px" ${ceAttr(key,'intro')}>${mdBold(tv(key,'intro',d.intro))}</div>
    <div style="background:#fff;padding:20px 22px;border:1px solid #e0e0e0">
      <div style="font-size:13px;color:#374151;line-height:1.9;white-space:pre-wrap" ${ceAttr(key,'points')}>${mdBold(tv(key,'points',d.points))}</div></div>
    <div style="font-size:12px;color:#9ca3af;margin-top:14px;text-align:right;font-style:italic">— Dr. K</div></div>`;
}

function renderGamescene(d,key){
  return `<div style="background:#1f2937;padding:28px 44px">
    <div style="font-size:22px;font-weight:900;color:#fff;margin-bottom:16px;padding-bottom:14px;border-bottom:1px solid #374151">${ts('gamescene')}</div>
    <img src="${d.imgUrl}" width="100%" style="display:block;max-width:552px;margin:0 auto;" onerror="this.style.display='none'">
    <div style="font-size:12px;color:#9ca3af;margin-top:14px;line-height:1.7">
      <strong style="color:#e5e7eb" ${ceAttr(key,'game')}>${tv(key,'game',d.game)}</strong> — <span ${ceAttr(key,'title')}>${tv(key,'title',d.title)}</span><br>
      "<span ${ceAttr(key,'comment')}>${tv(key,'comment',d.comment)}</span>" — Dr. K</div></div>`;
}

function renderMeme(d, key){
  let h = `<div style="background:#fff;padding:28px 44px;border-top:1px solid #e0e0e0">
    <div style="font-size:22px;font-weight:900;color:#000;margin-bottom:20px;padding-bottom:14px;border-bottom:1px solid #e0e0e0">${ts('meme')}</div>`;
    
  if (d.url || d.title) {
    let imgUrl = d.preview_img || d.thumbnail || d.url || '';
    if (imgUrl.includes('v.redd.it') || imgUrl.endsWith('.mp4') || imgUrl.endsWith('.webm')) imgUrl = ''; // 영상은 표시하지 않음
    
    const title = d.title || '';
    const subreddit = d.subreddit || '';
    const score = d.score || 0;
    const what_happened = d.what_happened || '';
    const one_liner = d.one_liner || '';
    const permalink = d.permalink || '#';

    h += `<div style="margin-bottom:20px;border:1px solid #e5e7eb">
      ${imgUrl ? `<a href="${permalink}" target="_blank" style="display:block"><img src="${imgUrl}" width="100%" style="display:block;max-width:100%" onerror="this.style.display='none'"></a>` : ''}
      <div style="padding:14px 16px">
        <div style="font-size:15px;font-weight:700;color:#111827;margin-bottom:8px" ${ceAttr(key,'title')}>${tv(key,'title',title)}</div>
        <div style="font-size:14px;font-weight:700;color:#374151;margin-bottom:4px">🤔 무슨 일인가요?</div>
        <div style="font-size:13px;color:#374151;line-height:1.6;margin-bottom:12px" ${ceAttr(key,'what_happened')}>${tv(key,'what_happened',what_happened)}</div>
        <div style="font-size:14px;font-weight:700;color:#374151;margin-bottom:4px">💬 오늘의 한마디</div>
        <div style="font-size:13px;color:#374151;line-height:1.6" ${ceAttr(key,'one_liner')}>${tv(key,'one_liner',one_liner)}</div>
        <div style="font-size:11px;color:#9ca3af;margin-top:12px">r/${subreddit} · 👍 ${score}</div>
      </div></div>`;
  } else {
    h += `<div style="font-size:13px;color:#9ca3af">밈 데이터가 없습니다. (수집 스크립트로 생성해 주세요)</div>`;
  }
  return h + '</div>';
}

function renderSoundtrack(d, key){
  const title = d.title || '';
  const channel = d.channel || '';
  const thumbnail = d.thumbnail || '';
  const url = d.url || '#';
  const comment = d.comment || '';
  let imgTag = '';
  if(thumbnail){
    imgTag = `<a href="${url}" target="_blank" style="display:block;position:relative;text-decoration:none">
      <img src="${thumbnail}" width="100%" style="display:block;max-width:100%" onerror="this.style.display='none'">
      <div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);width:60px;height:60px;background:rgba(0,0,0,0.7);border-radius:50%;display:flex;align-items:center;justify-content:center">
        <div style="width:0;height:0;border-style:solid;border-width:12px 0 12px 22px;border-color:transparent transparent transparent #fff;margin-left:4px"></div></div></a>`;
  }
  return `<div style="background:#111827;padding:28px 44px;border-top:1px solid #374151">
    <div style="font-size:22px;font-weight:900;color:#fff;margin-bottom:16px;padding-bottom:14px;border-bottom:1px solid #374151">${ts('soundtrack')}</div>
    ${imgTag}
    <div style="margin-top:14px">
      <div style="font-size:10px;font-weight:700;color:#e5e7eb;line-height:1.4">🎵 <span ${ceAttr(key,'title')}>${tv(key,'title',title)}</span></div>
      <div style="font-size:12px;color:#9ca3af;margin-top:4px" ${ceAttr(key,'channel')}>${tv(key,'channel',channel)}</div>
      <div style="font-size:13px;color:#9ca3af;margin-top:12px;line-height:1.7" ${ceAttr(key,'comment')}>${tv(key,'comment',comment)}</div>
      <a href="${url}" target="_blank" style="display:inline-block;margin-top:12px;background:#ef4444;color:#fff;font-size:12px;font-weight:700;padding:8px 20px;text-decoration:none">▶ ${t('youtubeListen')}</a>
    </div></div>`;
}

function renderTrailer(d, key){
  const title = d.title || '';
  const channel = d.channel || '';
  const thumbnail = d.thumbnail || '';
  const url = d.url || '#';
  const comment = d.comment || '';
  let imgTag = '';
  if(thumbnail){
    imgTag = `<a href="${url}" target="_blank" style="display:block;position:relative;text-decoration:none">
      <img src="${thumbnail}" width="100%" style="display:block;max-width:100%" onerror="this.style.display='none'">
      <div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);width:60px;height:60px;background:rgba(0,0,0,0.7);border-radius:50%;display:flex;align-items:center;justify-content:center">
        <div style="width:0;height:0;border-style:solid;border-width:12px 0 12px 22px;border-color:transparent transparent transparent #fff;margin-left:4px"></div></div></a>`;
  }
  return `<div style="background:#1e1b4b;padding:28px 44px;border-top:1px solid #312e81">
    <div style="font-size:22px;font-weight:900;color:#fff;margin-bottom:16px;padding-bottom:14px;border-bottom:1px solid #312e81">${ts('trailer')}</div>
    ${imgTag}
    <div style="margin-top:14px">
      <div style="font-size:10px;font-weight:700;color:#e5e7eb;line-height:1.4">🎬 <span ${ceAttr(key,'title')}>${tv(key,'title',title)}</span></div>
      <div style="font-size:12px;color:#94a3b8;margin-top:4px" ${ceAttr(key,'channel')}>${tv(key,'channel',channel)}</div>
      <div style="font-size:13px;color:#cbd5e1;margin-top:12px;line-height:1.7" ${ceAttr(key,'comment')}>${tv(key,'comment',comment)}</div>
      <a href="${url}" target="_blank" style="display:inline-block;margin-top:12px;background:#ef4444;color:#fff;font-size:12px;font-weight:700;padding:8px 20px;text-decoration:none">▶ ${t('youtubeWatch')}</a>
    </div></div>`;
}

function renderEpic(d, key){
  const epicCurrent = d.epic_current || (d.title ? [{title: d.title, thumbnail: d.thumbnail, url: d.url}] : []);
  const steamDeal = d.steam_deal;
  const comment = d.comment || '';
  
  const boldText = (txt) => txt.replace(/\*\*(.*?)\*\*/g, '<strong style="font-weight:900;color:#fff">$1</strong>').replace(/\n/g, '<br>');
  let commentHtml = boldText(tv(key, 'comment', comment));

  let epicComment = commentHtml;
  let steamComment = '';

  // AI가 생성한 '이번 주 무료 배포...' 같은 불필요한 타이틀을 제거
  epicComment = epicComment.replace(/<strong style="font-weight:900;color:#fff">\[이번 주 무료 배포 - 에픽게임즈 스토어\]<\/strong>(<br>)?/ig, '').replace(/\[이번 주 무료 배포 - 에픽게임즈 스토어\](<br>)?/ig, '').trim();
  epicComment = epicComment.replace(/^(<br>|\s)+/, '');

  // 텍스트에서 스팀 부분 분리
  const steamSplit = epicComment.split(/<strong style="font-weight:900;color:#fff">\[스팀 주말 혜택\]<\/strong>|\[스팀 주말 혜택\]/i);
  if(steamSplit.length > 1){
      epicComment = steamSplit[0].replace(/(<br>|\s)+$/, '');
      steamComment = steamSplit[1].replace(/^(<br>|\s)+/, '');
  }

  let epicCards = '';
  epicCurrent.forEach((game, i) => {
    const gTitle = game.title || '게임 명';
    const gThumb = game.thumbnail || '';
    const gUrl = game.url || '#';
    
    epicCards += `
      <div style="flex:1; min-width:200px; background:#1a1a1a;border-radius:12px;overflow:hidden;border:1px solid #333">
          <a href="${gUrl}" target="_blank" style="display:block;text-decoration:none">
              <img src="${gThumb}" style="width:100%;display:block;aspect-ratio:16/9;object-fit:cover;" onerror="this.style.display='none'">
          </a>
          <div style="padding:16px">
              <div style="font-size:14px;font-weight:800;color:#fff;margin-bottom:8px;line-height:1.4;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;text-overflow:ellipsis">${gTitle}</div>
              <a href="${gUrl}" target="_blank" style="display:inline-block;background:#fff;color:#000;font-size:12px;font-weight:800;padding:8px 16px;text-decoration:none;border-radius:6px">FREE GET</a>
          </div>
      </div>`;
  });
  const epicCardsContainer = `<div style="display:flex; flex-wrap:wrap; gap:16px; margin-bottom:24px">${epicCards}</div>`;

  let steamCard = '';
  if(steamDeal){
    const sTitle = steamDeal.name || 'Steam Deal';
    const sThumb = steamDeal.thumbnail || '';
    const sUrl = steamDeal.url || '#';
    const sDiscount = steamDeal.discount_percent || 0;
    const sPrice = steamDeal.final_price || '';
    const steamCommentHtml = steamComment ? `<div style="font-size:13px;color:#cbd5e1;line-height:1.6;margin-bottom:16px;white-space:pre-line">${steamComment}</div>` : '';

    steamCard = `
      <div style="margin-top:40px; padding-top:32px; border-top:1px dashed #4b5563;">
          <div style="background:#0e1c2f;border-radius:12px;padding:16px;border:1px solid #1e3a5f">
              <div style="font-size:11px;font-weight:800;color:#66c0f4;text-transform:uppercase;margin-bottom:12px;letter-spacing:1px">🔥 STEAM WEEKEND DEAL</div>
              <a href="${sUrl}" target="_blank" style="display:block;text-decoration:none;margin-bottom:14px">
                  <img src="${sThumb}" width="100%" style="display:block;max-width:100%;border-radius:8px" onerror="this.style.display='none'">
              </a>
              ${steamCommentHtml}
              <div style="display:flex;justify-content:flex-end;align-items:center;margin-top:4px">
                  <span style="background:#4c6b22;color:#a3d200;padding:6px 10px;font-weight:900;border-radius:4px;font-size:13px;margin-right:12px">-${sDiscount}%</span>
                  <a href="${sUrl}" target="_blank" style="background:#1b2838;color:#fff;border:1px solid #66c0f4;font-size:11px;font-weight:800;padding:10px 32px;text-decoration:none;border-radius:4px;display:inline-block;letter-spacing:0.5px">VIEW ON STEAM</a>
              </div>
          </div>
      </div>`;
  }

  return `<div style="background:#000;padding:32px 44px;color:#fff">
    <div style="font-size:24px;font-weight:900;color:#fff;margin-bottom:24px;padding-bottom:14px;border-bottom:1px solid #333">${ts('epic')}</div>
    ${epicCardsContainer}
    <div style="font-size:14px;color:#9ca3af;margin-top:12px;line-height:1.7;white-space:pre-line" ${ceAttr(key,'comment')}>${epicComment}</div>
    ${steamCard}
  </div>`;
}

function renderChart(d){
  function col(title,data,ckey,width){
    let h=`<div style="width:${width};display:inline-block;vertical-align:top;padding:0 4px">
      <div style="overflow:hidden;border:1px solid #e5e7eb">
      <div style="background:#1f2937;padding:10px 14px;font-size:11px;font-weight:800;color:#fff;white-space:nowrap">${title}</div><div style="padding:12px 14px">`;
    data.forEach((r,i)=>{
      const rank=i+1; const rc=rank===1?'#f59e0b':'#9ca3af';
      h+=`<div class="item-row" draggable="true" ondragstart="onDragStart('chart','${ckey}',${i},event)" ondragend="onDragEnd(event)" ondragover="onDragOver(event)" ondrop="onDropChart('${ckey}',${i},event)"
        style="font-size:12px;padding:7px 0;${i<data.length-1?'border-bottom:1px solid #f3f4f6;':''}color:#111827;cursor:grab">
        <span style="color:${rc};font-weight:800;margin-right:6px">${rank}</span>
        <span contenteditable="true" data-sec="chart" data-field="${ckey}.${i}.game" onblur="onCEBlur(this)">${r.game}</span>
        ${r.change?` <span style="color:#10b981;font-size:10px;font-weight:700">${r.change}</span>`:''}
        <button class="btn-del-item" style="position:static;transform:none;opacity:0;float:right" onmouseover="this.style.opacity=1" onmouseout="this.style.opacity=0" onclick="delChartItem('${ckey}',${i})">✕</button></div>`;
    });
    h+=`</div></div><button class="btn-add-item" style="margin-top:4px" onclick="addChartItem('${ckey}')">+</button></div>`;
    return h;
  }
  const cc = (I18N[curLang]||I18N.ko).chartCols;
  return `<div style="background:#fff;padding:28px 44px">
    <div style="font-size:20px;font-weight:800;color:#1f2937;margin-bottom:20px;padding-bottom:14px;border-bottom:2px solid #e0e0e0">${ts('chart')}</div>
    <div style="display:flex;gap:8px">
    ${col(cc[0],d.pc,'pc','30%')}${col(cc[1],d.console,'console','33%')}${col(cc[2],d.mobile,'mobile','37%')}</div></div>`;
}

// ── SECTION CONTROLS ──
function toggleSection(key,on){ cur().sections[key].enabled=on; save(); render(); }
function regenerate(key){
  const el=document.getElementById('content-'+key);
  el.classList.add('regenerating');
  setTimeout(()=>{ el.classList.remove('regenerating'); toast('🔄 재생성 완료 (데모)'); },1500);
}

// ── ADD / DELETE ──
function delItem(sec,arr,i){ cur().sections[sec][arr].splice(i,1); save(); render(); }
function addRelease(){ cur().sections.calendar.releases.push({game:'새 게임',dev:'개발사',date:'날짜',platforms:['PC'],color:randColor(),note:''}); save(); render(); }
function addEvent(){ cur().sections.calendar.events.push({name:'새 이벤트',note:'',venue:'장소',date:'날짜',tag:'이벤트'}); save(); render(); }
function addBriefing(){
  const tp=TAG_PRESETS[0];
  cur().sections.briefing.items.push({tag:tp.tag,tagBg:tp.bg,tagColor:tp.c,title:'뉴스 제목',source:'출처',time:'시간'});
  save(); render();
}
function cycleBriefingTag(i){
  const item=cur().sections.briefing.items[i];
  const ci=TAG_PRESETS.findIndex(t=>t.tag===item.tag);
  const next=TAG_PRESETS[(ci+1)%TAG_PRESETS.length];
  item.tag=next.tag; item.tagBg=next.bg; item.tagColor=next.c;
  save(); render();
}
function addFeedbackItem(){
  const f=cur().sections.feedback; if(!f.items) f.items=[];
  f.items.push({game:'신규 게임',period:'출시 초기',count:'0',sources:'커뮤니티',score:'0.0',pos:0,neu:100,neg:0,keywords:[],comments:[]});
  save(); render();
}
function addKeyword(idx){
  const text=prompt('키워드를 입력하세요:'); if(!text) return;
  const positive=confirm('긍정적 키워드입니까?\n[확인]=긍정(녹색) / [취소]=부정(빨강)');
  const item = cur().sections.feedback.items ? cur().sections.feedback.items[idx] : cur().sections.feedback;
  item.keywords.push({text,positive}); save(); render();
}
function delKeyword(idx,ki){
  const item = cur().sections.feedback.items ? cur().sections.feedback.items[idx] : cur().sections.feedback;
  item.keywords.splice(ki,1); save(); render();
}
function toggleKwSentiment(idx,ki){
  const item = cur().sections.feedback.items ? cur().sections.feedback.items[idx] : cur().sections.feedback;
  item.keywords[ki].positive = !item.keywords[ki].positive; save(); render();
}
function addFeedbackComment(idx){
  const item = cur().sections.feedback.items ? cur().sections.feedback.items[idx] : cur().sections.feedback;
  item.comments.push({text:'코멘트 내용',meta:'출처',positive:true}); save(); render();
}
function delFeedbackComment(idx,ci){
  const item = cur().sections.feedback.items ? cur().sections.feedback.items[idx] : cur().sections.feedback;
  item.comments.splice(ci,1); save(); render();
}
function addPollOption(){ cur().sections.poll.options.push({text:'새 항목',link:'https://'}); save(); render(); }
function addChartItem(key){ cur().sections.chart[key].push({game:'게임명',change:''}); save(); render(); }
function delChartItem(key,i){ cur().sections.chart[key].splice(i,1); save(); render(); }
function onDropChart(ckey,toIdx,e){
  e.preventDefault();
  if(!dragState||dragState.arr!==ckey) return;
  const list=cur().sections.chart[ckey], item=list.splice(dragState.from,1)[0];
  list.splice(toIdx,0,item); save(); render();
}

// TAG add/del for platforms
function delTag(sec,arr,itemIdx,tagIdx){ cur().sections[sec][arr][itemIdx].platforms.splice(tagIdx,1); save(); render(); }
function addTag(sec,arr,itemIdx){
  const p=prompt('플랫폼 (PC, PS5, Xbox, Mobile, Switch):');
  if(!p) return;
  cur().sections[sec][arr][itemIdx].platforms.push(p.trim()); save(); render();
}

// ── SAVE ──
function saveEdition(){
  if(!editions.length || curIdx < 0){ toast('⚠️ 에디션이 없습니다'); return; }
  const btn = document.querySelector('.tbtn-primary');
  btn.disabled = true; btn.textContent = '⏳ 저장 중...';
  fetch('/api/save-edition', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify(cur())
  }).then(r => r.json()).then(res => {
    if(res.ok) toast(`💾 서버 저장 완료 (${res.file})`);
    else toast('❌ 저장 실패: ' + (res.error||''));
  }).catch(e => toast('❌ 서버 연결 실패: ' + e.message))
  .finally(() => { btn.disabled = false; btn.textContent = '💾 저장'; });
}

// ── SCHEDULE ──
function openModal(name){
  document.getElementById(name+'Backdrop').classList.add('open');
  document.getElementById(name+'Modal').classList.add('open');
  if(name==='schedule'){
    const s=cur().schedule;
    document.getElementById('schedDate').value=s.date||new Date(Date.now()+86400000).toISOString().slice(0,10);
    document.getElementById('schedTime').value=s.time||'07:00';
    document.getElementById('btnCancelSched').style.display=cur().status==='scheduled'?'':'none';
  }
}
function closeModal(name){
  document.getElementById(name+'Backdrop').classList.remove('open');
  document.getElementById(name+'Modal').classList.remove('open');
}
function confirmSchedule(){
  const d=document.getElementById('schedDate').value, t=document.getElementById('schedTime').value;
  if(!d){ toast('⚠️ 날짜를 선택하세요'); return; }
  const target=document.querySelector('input[name=target]:checked').value;
  const langs=['ko','en','ja'];
  cur().schedule={date:d,time:t,target,languages:langs}; cur().status='scheduled';
  save(); renderSidebar(); updateSchedBanner(); closeModal('schedule');
  // Auto-export JSON for publish_edition.py
  exportEditionJSON();
  toast(`📅 ${d} ${t} 발송 예약 완료! (JSON 내보내기됨)`);
}
function testSend(){
  if(!editions.length || curIdx < 0){ toast('⚠️ 에디션이 없습니다'); return; }
  const btn = document.getElementById('btnTestSend');
  btn.disabled = true; btn.textContent = '⏳ 발송 중...';
  const data = JSON.stringify(cur());
  fetch('/api/test-send', {method:'POST', headers:{'Content-Type':'application/json'}, body:data})
    .then(r => r.json())
    .then(res => {
      if(res.ok) toast(`✅ 테스트 발송 완료! ${res.to}`);
      else toast('❌ 발송 실패: ' + (res.error||''));
    })
    .catch(e => toast('❌ 서버 연결 실패: ' + e.message))
    .finally(() => { btn.disabled = false; btn.textContent = '📧 테스트 발송'; });
}
async function openPreview(){
  if(!editions.length || curIdx < 0){ toast('⚠️ 에디션이 없습니다'); return; }
  // Build clean newsletter HTML with only enabled sections
  const ed = cur();
  const s = ed.sections;
  let body = '';
  // Header
  body += renderHeader();
  // Section renderers map
  const secDefs = [
    {key:'calendar', fn:renderCalendar},
    {key:'briefing', fn:renderBriefing},
    {key:'feedback', fn:renderFeedback},
    {key:'drk', fn:renderDrK},
    {key:'gamescene', fn:renderGamescene},
    {key:'meme', fn:renderMeme},
    {key:'soundtrack', fn:renderSoundtrack},
    {key:'trailer', fn:renderTrailer},
    {key:'epic', fn:renderEpic},
    {key:'chart', fn:renderChart},
    {key:'newsletter_feedback', fn:renderNewsletterFeedback},
    {key:'poll', fn:renderPoll}
  ];
  secDefs.forEach(sec => {
    if(s[sec.key] && s[sec.key].enabled){
      body += sec.fn(s[sec.key], sec.key);
    }
  });
  // Create clean HTML document
  const tmp = document.createElement('div');
  tmp.innerHTML = body;
  // Strip ALL editor controls
  tmp.querySelectorAll('.btn-del-item, .btn-add-item, .btn-add-tag, .tag-x, .btn-add-comment, input[type=hidden], .sec-ctrl, .sec-wrap.disabled').forEach(el => el.remove());
  tmp.querySelectorAll('[contenteditable]').forEach(el => el.removeAttribute('contenteditable'));
  tmp.querySelectorAll('[draggable]').forEach(el => { el.removeAttribute('draggable'); el.style.cursor = 'default'; });
  tmp.querySelectorAll('[onclick]').forEach(el => el.removeAttribute('onclick'));
  tmp.querySelectorAll('[onblur]').forEach(el => el.removeAttribute('onblur'));
  tmp.querySelectorAll('[ondragstart]').forEach(el => el.removeAttribute('ondragstart'));
  tmp.querySelectorAll('[ondragend]').forEach(el => el.removeAttribute('ondragend'));
  tmp.querySelectorAll('[ondragover]').forEach(el => el.removeAttribute('ondragover'));
  tmp.querySelectorAll('[ondrop]').forEach(el => el.removeAttribute('ondrop'));
  
  const html = `<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Preview #${ed.num} (${curLang.toUpperCase()})</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
<style>body{font-family:'Inter',sans-serif;background:#f0f4f8;display:flex;justify-content:center;padding:40px;margin:0}.wrap{width:640px;max-width:100%;background:#fff}
@media(max-width:480px){body{padding:0}.wrap{width:100%}
.nl-sec{padding:14px 0 !important}.nl-sec-head{padding:18px 0 14px !important}
.nl-chart-row{display:block !important}.nl-chart-col{display:block !important;width:100% !important;margin-bottom:12px;padding:0 !important}
.nl-fb-row{display:block !important}.nl-fb-btn{display:block !important;width:100% !important;margin-bottom:8px}
.nl-score-box{display:block !important}
div, span, p { word-break: keep-all !important; overflow-wrap: break-word !important; }
div[style*="font-size:20px"]{font-size:26px !important; margin-bottom:24px !important}div[style*="font-size:14px"]{font-size:17px !important; line-height:1.6 !important}
div[style*="font-size:17px"]{font-size:22px !important; line-height:1.4 !important}div[style*="font-size:32px"]{font-size:30px !important}
div[style*="font-size:13px"]{font-size:16px !important; line-height:1.7 !important}div[style*="font-size:15px"]{font-size:19px !important; line-height:1.5 !important}
div[style*="font-size:24px"]{font-size:34px !important}div[style*="font-size:11px"]{font-size:14px !important}
div[style*="font-size:12px"]{font-size:15px !important}div[style*="font-size:10px"]{font-size:13px !important}}</style></head>
<body><div class="wrap">${tmp.innerHTML}</div></body></html>`;
  
  const w = window.open('', '_blank', 'width=720,height=900');
  w.document.write(html);
  w.document.close();
  toast('👁 최종 뉴스레터 미리보기');
}
function exportEditionJSON(){
  const data = JSON.stringify(cur(), null, 2);
  // Try server save first, fallback to download
  fetch('/api/save-edition', {method:'POST', headers:{'Content-Type':'application/json'}, body:data})
    .then(r => r.json())
    .then(res => { if(res.ok) toast(`💾 ${res.file} 서버에 저장됨`); else throw new Error(res.error); })
    .catch(() => {
      // Fallback: browser download
      const blob = new Blob([data], {type:'application/json'});
      const a = document.createElement('a'); a.href = URL.createObjectURL(blob);
      a.download = `edition_${cur().num}.json`; document.body.appendChild(a);
      a.click(); document.body.removeChild(a); URL.revokeObjectURL(a.href);
      toast('📥 JSON 다운로드됨 (서버 미연결)');
    });
}
function cancelSchedule(){
  cur().status='draft'; cur().schedule={date:'',time:'07:00',target:'all',languages:['ko','en']};
  save(); renderSidebar(); updateSchedBanner(); closeModal('schedule'); toast('예약 취소됨');
}

// ── TOAST ──
function toast(msg){ const t=document.getElementById('toast'); t.textContent=msg; t.classList.add('show'); setTimeout(()=>t.classList.remove('show'),2500); }

// ── JSON IMPORT ──
function importJSON(input){
  const file = input.files[0];
  if(!file) return;
  const reader = new FileReader();
  reader.onload = function(e){
    try {
      let data = JSON.parse(e.target.result);
      // Validate required fields
      if(!data.sections){ toast('⚠️ 유효하지 않은 JSON: sections 필드가 없습니다'); return; }
      // XSS 방지: 모든 문자열 필드를 이스케이프
      data = sanitizeStrings(data);
      // Ensure all required fields exist
      if(!data.num) data.num = String(editions.length+1).padStart(3,'0');
      if(!data.date) data.date = new Date().toISOString().slice(0,10);
      if(!data.status) data.status = 'draft';
      if(!data.schedule) data.schedule = {date:'',time:'07:00',target:'all',languages:['ko','en']};
      if(!data.translations) data.translations = {en:{},ja:{}};
      // Add to editions
      editions.push(data);
      curIdx = editions.length - 1;
      save(); renderSidebar(); loadEdition(curIdx);
      toggleSidebar();
      toast(`📂 에디션 #${escapeHtml(data.num)} 불러오기 완료`);
    } catch(err){
      toast('⚠️ JSON 파싱 오류: ' + escapeHtml(err.message));
    }
  };
  reader.readAsText(file, 'UTF-8');
  input.value = ''; // reset for re-import
}

init();

function sendToGhostDraft(){
  if(!editions.length || curIdx < 0){ toast('⚠️ 에디션이 없습니다'); return; }
  if(!confirm('Ghost에 Draft(임시저장) 상태로 내보내시겠습니까?\n이후 Ghost 어드민에서 시간을 지정해 최종 예약을 진행해주세요.')) return;
  const btn = document.querySelector('button[onclick="sendToGhostDraft()"]');
  btn.disabled = true; btn.textContent = '⏳ 내보내는 중...';
  
  save(true);
  
  fetch('/api/send-draft', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify(cur())
  }).then(r => r.json()).then(res => {
    if(res.ok) toast(`✅ Ghost 임시저장 완료! Ghost 어드민을 확인하세요.`);
    else toast('❌ 내보내기 실패: ' + (res.error||''));
  }).catch(e => toast('❌ 서버 연결 실패: ' + e.message))
  .finally(() => { btn.disabled = false; btn.textContent = '📤 Ghost 임시저장'; });
}

function confirmSchedule(){
  const d=document.getElementById('schedDate').value, t=document.getElementById('schedTime').value;
  if(!d){ toast('⚠️ 날짜를 선택하세요'); return; }
  const target=document.querySelector('input[name=target]:checked').value;
  const langs=['ko','en','ja'];
  
  // Update local state
  cur().schedule={date:d,time:t,target,languages:langs}; 
  cur().status='scheduled';
  
  save(); 
  saveEdition(); // PUSH STATE TO PYTHON SERVER OR IT WILL RUN DRY
  renderSidebar(); 
  updateSchedBanner(); 
  closeModal('schedule');
  
  toast('📅 로컬 예약 정보가 저장되었습니다. (백그라운드 스케줄러가 알아서 발송합니다)');
}
