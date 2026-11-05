/**
 * Google Apps Script — GTPlayer 올인원 백엔드 (구독 / 수신거부 / 동기화 / 피드백 / 클릭 트래커)
 * 
 * 하나의 웹앱에서 다음 기능을 통합 처리:
 *   1. 뉴스레터 수신거부 (action=unsubscribe) -> 즉시 구독 해제 및 확인 페이지 렌더링
 *   2. 뉴스레터 구독 (action=subscribe) -> 이메일 수집 및 Subscribers 시트 저장
 *   3. 활성 구독자 목록 동기화 (action=list) -> scheduled_publish.py 에서 자동 fetch
 *   4. 뉴스레터 피드백 (vote=up/down) -> Feedback 시트 기록 및 감사 페이지
 *   5. 링크 클릭 트래킹 (url=...) -> ClickLog 시트 기록 및 목적지 리다이렉트
 * 
 * 시트 구조:
 *   - Subscribers: [Timestamp, Email, Subscribed, Language, Created_At, Updated_At]
 *   - Feedback:    [Timestamp, Edition, Vote, Language, Member UUID, Country, City]
 *   - ClickLog:    [Timestamp, Edition, Section, Label, Language, URL]
 * 
 * 배포 방법:
 *   1. Google Sheets의 확장 프로그램 > Apps Script 열기
 *   2. 기존 코드를 이 코드로 전체 교체
 *   3. 오른쪽 상단 [배포] > [배포 관리] > 연필(수정) 아이콘 클릭
 *   4. 버전: [새 버전] 선택 > [배포] 클릭
 */

function doGet(e) {
  e = e || { parameter: {} };
  var action = (e.parameter.action || '').toLowerCase();
  var url    = e.parameter.url || '';
  var vote   = e.parameter.vote || '';

  if (action === 'unsubscribe') {
    return handleUnsubscribe(e);
  } else if (action === 'subscribe') {
    return handleSubscribe(e);
  } else if (action === 'list') {
    return handleListSubscribers(e);
  } else if (url) {
    return handleClickTrack(e);
  } else if (vote) {
    return handleFeedback(e);
  } else {
    return HtmlService.createHtmlOutput('<h2>GTPlayer Web App is active.</h2>');
  }
}

function doPost(e) {
  e = e || { parameter: {} };
  var action = (e.parameter.action || '').toLowerCase();
  if (action === 'subscribe' || !action) {
    return handleSubscribe(e);
  }
  return doGet(e);
}


// ════════════════════════════════════════════
//  1. 수신거부 (Unsubscribe) 핸들러
// ════════════════════════════════════════════

function handleUnsubscribe(e) {
  var email = (e.parameter.email || '').trim().toLowerCase();
  var lang  = (e.parameter.lang || 'ko').toLowerCase();

  var i18n = {
    'ko': {
      title: '수신거부 완료 · GTPlayer',
      heading: '구독이 정상적으로 취소되었습니다.',
      desc: '더 이상 GTPlayer 뉴스레터가 발송되지 않습니다. 그동안 함께해 주셔서 감사했습니다.',
      undo: '실수로 취소하셨나요?',
      resub: '다시 구독하기'
    },
    'en': {
      title: 'Unsubscribed · GTPlayer',
      heading: 'You have been unsubscribed.',
      desc: 'You will no longer receive the GTPlayer newsletter. Thank you for reading with us.',
      undo: 'Unsubscribed by mistake?',
      resub: 'Resubscribe'
    },
    'ja': {
      title: '配信停止完了 · GTPlayer',
      heading: 'ニュースレターの配信を停止しました。',
      desc: '今後のニュースレター配信は行われません。これまでご愛読いただき誠にありがとうございました。',
      undo: '誤って停止しましたか？',
      resub: '再購読する'
    }
  };
  var t = i18n[lang] || i18n['ko'];

  if (email && email.indexOf('@') !== -1) {
    try {
      var ss = SpreadsheetApp.getActiveSpreadsheet();
      var sheet = ss.getSheetByName('Subscribers');
      if (!sheet) {
        sheet = ss.insertSheet('Subscribers');
        sheet.appendRow(['Timestamp', 'Email', 'Subscribed', 'Language', 'Created_At', 'Updated_At']);
        sheet.getRange(1, 1, 1, 6).setFontWeight('bold');
        sheet.setFrozenRows(1);
      }
      var data = sheet.getDataRange().getValues();
      var found = false;
      var nowStr = Utilities.formatDate(new Date(), "Asia/Seoul", "yyyy-MM-dd HH:mm:ss");
      for (var i = 1; i < data.length; i++) {
        if ((data[i][1] || '').toString().trim().toLowerCase() === email) {
          sheet.getRange(i + 1, 3).setValue(0); // 0 = 구독취소
          sheet.getRange(i + 1, 6).setValue(nowStr); // Updated_At
          found = true;
          break;
        }
      }
      if (!found) {
        sheet.appendRow([nowStr, email, 0, lang, nowStr, nowStr]);
      }
    } catch (err) {
      Logger.log('Unsubscribe error: ' + err.toString());
    }
  }

  var resubUrl = 'https://www.gtplayer.net/' + (lang === 'ko' ? '' : lang + '/');

  var html = `<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
  <title>${t.title}</title>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800;900&display=swap" rel="stylesheet">
  <style>
    * { box-sizing: border-box; }
    body { font-family: 'Inter', -apple-system, sans-serif; background: #0f1115; color: #f3f4f6; display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; padding: 20px; }
    .card { background: #181a20; border: 1px solid #2d3139; border-radius: 16px; padding: 48px 36px; text-align: center; max-width: 440px; width: 100%; box-shadow: 0 20px 40px rgba(0,0,0,0.5); }
    .icon { font-size: 44px; margin-bottom: 20px; line-height: 1; }
    .title { font-size: 22px; font-weight: 800; color: #ffffff; margin: 0 0 12px 0; letter-spacing: -0.5px; }
    .desc { font-size: 14px; line-height: 1.6; color: #9ca3af; margin: 0 0 24px 0; word-break: keep-all; }
    .email-badge { display: inline-block; background: #262933; color: #d1d5db; padding: 6px 14px; border-radius: 20px; font-size: 13px; margin-bottom: 28px; font-family: monospace; border: 1px solid #374151; }
    .btn { display: inline-block; background: #ffffff; color: #000000; text-decoration: none; padding: 12px 24px; border-radius: 8px; font-size: 14px; font-weight: 700; transition: opacity 0.2s; }
    .btn:hover { opacity: 0.9; }
    .undo-text { font-size: 12px; color: #6b7280; margin-bottom: 10px; }
    .brand { margin-top: 36px; font-size: 12px; font-weight: 900; letter-spacing: 1.5px; color: #4b5563; }
  </style></head><body>
  <div class="card">
    <div class="icon">✉️</div>
    <h1 class="title">${t.heading}</h1>
    <p class="desc">${t.desc}</p>
    ${email ? `<div class="email-badge">${email}</div>` : ''}
    <div>
      <div class="undo-text">${t.undo}</div>
      <a href="${resubUrl}" class="btn">${t.resub}</a>
    </div>
    <div class="brand">GTPLAYER</div>
  </div>
  </body></html>`;

  return HtmlService.createHtmlOutput(html).setTitle(t.title);
}


// ════════════════════════════════════════════
//  2. 구독 (Subscribe) 핸들러
// ════════════════════════════════════════════

function handleSubscribe(e) {
  var email = '';
  var lang = 'ko';

  if (e.parameter && e.parameter.email) {
    email = e.parameter.email;
    lang  = e.parameter.lang || 'ko';
  } else if (e.postData && e.postData.contents) {
    try {
      var body = JSON.parse(e.postData.contents);
      email = body.email || '';
      lang  = body.lang || 'ko';
    } catch(err) {
      email = e.postData.contents;
    }
  }

  email = (email || '').trim().toLowerCase();
  lang  = (lang || 'ko').toLowerCase();

  if (!email || email.indexOf('@') === -1) {
    return ContentService.createTextOutput(JSON.stringify({ status: 'error', message: 'Invalid email' }))
      .setMimeType(ContentService.MimeType.JSON);
  }

  try {
    var ss = SpreadsheetApp.getActiveSpreadsheet();
    var sheet = ss.getSheetByName('Subscribers');
    if (!sheet) {
      sheet = ss.insertSheet('Subscribers');
      sheet.appendRow(['Timestamp', 'Email', 'Subscribed', 'Language', 'Created_At', 'Updated_At']);
      sheet.getRange(1, 1, 1, 6).setFontWeight('bold');
      sheet.setFrozenRows(1);
    }

    var data = sheet.getDataRange().getValues();
    var found = false;
    var nowStr = Utilities.formatDate(new Date(), "Asia/Seoul", "yyyy-MM-dd HH:mm:ss");

    for (var i = 1; i < data.length; i++) {
      if ((data[i][1] || '').toString().trim().toLowerCase() === email) {
        sheet.getRange(i + 1, 3).setValue(1); // 1 = 구독자
        sheet.getRange(i + 1, 4).setValue(lang);
        sheet.getRange(i + 1, 6).setValue(nowStr);
        found = true;
        break;
      }
    }
    if (!found) {
      sheet.appendRow([nowStr, email, 1, lang, nowStr, nowStr]);
    }

    return ContentService.createTextOutput(JSON.stringify({ status: 'ok', message: 'subscribed', email: email }))
      .setMimeType(ContentService.MimeType.JSON);
  } catch(err) {
    return ContentService.createTextOutput(JSON.stringify({ status: 'error', message: err.toString() }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}


// ════════════════════════════════════════════
//  3. 활성 구독자 목록 동기화 (List)
// ════════════════════════════════════════════

function handleListSubscribers(e) {
  try {
    var ss = SpreadsheetApp.getActiveSpreadsheet();
    var sheet = ss.getSheetByName('Subscribers');
    if (!sheet) {
      return ContentService.createTextOutput(JSON.stringify({ subscribers: [] }))
        .setMimeType(ContentService.MimeType.JSON);
    }
    var data = sheet.getDataRange().getValues();
    var list = [];
    for (var i = 1; i < data.length; i++) {
      var em = (data[i][1] || '').toString().trim().toLowerCase();
      var sub = data[i][2];
      var lg = (data[i][3] || 'ko').toString().trim().toLowerCase();
      if (em && (sub === 1 || sub === '1' || sub === true || sub === 'TRUE' || sub === 'true')) {
        list.push({ email: em, lang: lg, subscribed: true });
      }
    }
    return ContentService.createTextOutput(JSON.stringify({ subscribers: list }))
      .setMimeType(ContentService.MimeType.JSON);
  } catch(err) {
    return ContentService.createTextOutput(JSON.stringify({ subscribers: [], error: err.toString() }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}


// ════════════════════════════════════════════
//  4. 클릭 트래킹 핸들러 (기존)
// ════════════════════════════════════════════

function handleClickTrack(e) {
  var edition = e.parameter.edition || '';
  var section = e.parameter.section || '';
  var label   = e.parameter.label || '';
  var lang    = e.parameter.lang || 'ko';
  var url     = e.parameter.url || '';

  if (!url || (url.indexOf('http://') !== 0 && url.indexOf('https://') !== 0)) {
    return HtmlService.createHtmlOutput(
      '<html><body style="font-family:Inter,sans-serif;text-align:center;padding:60px">' +
      '<h2>⚠️ Invalid URL</h2></body></html>'
    );
  }

  try {
    var ss    = SpreadsheetApp.getActiveSpreadsheet();
    var sheet = ss.getSheetByName('ClickLog');
    if (!sheet) {
      sheet = ss.insertSheet('ClickLog');
      sheet.appendRow(['Timestamp', 'Edition', 'Section', 'Label', 'Language', 'URL']);
      sheet.getRange(1, 1, 1, 6).setFontWeight('bold');
      sheet.setFrozenRows(1);
    }
    sheet.insertRowAfter(1);
    sheet.getRange(2, 1, 1, 6).setValues([[
      Utilities.formatDate(new Date(), "Asia/Seoul", "yyyy-MM-dd HH:mm:ss"),
      edition,
      section,
      label,
      lang,
      url
    ]]);
  } catch (err) {
    Logger.log('Click logging error: ' + err.toString());
  }

  var safeUrl = url
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

  var jsUrl = url
    .replace(/\\/g, '\\\\')
    .replace(/"/g, '\\"')
    .replace(/'/g, "\\'");

  var html = '<!DOCTYPE html><html><head>'
    + '<meta charset="UTF-8">'
    + '<meta http-equiv="refresh" content="0;url=' + safeUrl + '">'
    + '<script>window.location.replace("' + jsUrl + '");</script>'
    + '</head>'
    + '<body style="font-family:Inter,sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;background:#f9fafb">'
    + '<div style="text-align:center">'
    + '<p style="color:#666;font-size:14px">Redirecting...</p>'
    + '<p style="margin-top:16px"><a href="' + safeUrl + '" style="color:#2563eb;font-size:13px">Click here if not redirected</a></p>'
    + '<p style="margin-top:24px;color:#ccc;font-size:11px;font-weight:900;letter-spacing:1px">GTPLAYER</p>'
    + '</div></body></html>';

  return HtmlService.createHtmlOutput(html).setTitle('GTPlayer — Redirecting');
}


// ════════════════════════════════════════════
//  5. 피드백 핸들러 (기존)
// ════════════════════════════════════════════

function handleFeedback(e) {
  try {
    var vote = e.parameter.vote || '';
    var edition = e.parameter.edition || '';
    var lang = e.parameter.lang || 'ko';
    var member = e.parameter.member || '';
    
    if (!vote || !edition) {
      return HtmlService.createHtmlOutput('<h2>잘못된 요청입니다.</h2>');
    }

    var ss = SpreadsheetApp.getActiveSpreadsheet();
    var sheet = ss.getSheetByName('Feedback');
    if (!sheet) {
      sheet = ss.insertSheet('Feedback');
      sheet.appendRow(['Timestamp', 'Edition', 'Vote', 'Language', 'Member UUID', 'Country', 'City']);
    }

    var countryStr = e.parameter.country || 'N/A';
    var cityStr = e.parameter.city || 'N/A';

    sheet.insertRowAfter(1);
    sheet.getRange(2, 1, 1, 7).setValues([[
      Utilities.formatDate(new Date(), "Asia/Seoul", "yyyy-MM-dd HH:mm:ss"),
      "'" + edition,
      vote,
      lang,
      member,
      countryStr,
      cityStr
    ]]);

    var emoji = (vote === 'up') ? '👍' : '👎';
    var i18n = {
      'ko': { thanks: '피드백 감사합니다!', msg: '소중한 의견이 반영됩니다.', close: '이 탭을 닫아주세요.' },
      'en': { thanks: 'Thank you for your feedback!', msg: 'Your opinion matters to us.', close: 'You may close this tab.' },
      'ja': { thanks: 'フィードバックありがとうございます！', msg: 'ご意見は大切に活用いたします。', close: 'このタブを閉じてください。' }
    };
    var t = i18n[lang] || i18n['ko'];
    
    var html = `<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap" rel="stylesheet">
    <style>
      body { font-family: 'Inter', sans-serif; background: #f5f5f5; display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; }
      .card { background: #fff; border: 2px solid #000; padding: 48px 40px; text-align: center; max-width: 400px; }
      .emoji { font-size: 48px; margin-bottom: 16px; }
      .thanks { font-size: 20px; font-weight: 900; color: #000; margin-bottom: 8px; }
      .msg { font-size: 14px; color: #666; margin-bottom: 24px; }
      .close { font-size: 12px; color: #999; }
      .brand { font-size: 14px; font-weight: 900; color: #000; margin-top: 24px; letter-spacing: 1px; }
    </style></head><body>
    <div class="card">
      <div class="emoji">${emoji}</div>
      <div class="thanks">${t.thanks}</div>
      <div class="msg">${t.msg}</div>
      <div class="close">${t.close}</div>
      <div class="brand">GTPlayer</div>
    </div></body></html>`;
    
    return HtmlService.createHtmlOutput(html).setTitle('GTPlayer Feedback');
  } catch (err) {
    return HtmlService.createHtmlOutput('<h2>오류: ' + err.toString() + '</h2>');
  }
}
