/**
 * Google Apps Script — 뉴스레터 피드백 + 클릭 트래커 통합
 * 
 * 하나의 웹앱에서 두 가지 기능을 처리:
 *   1. 피드백 수집 (vote 파라미터가 있으면)
 *   2. 클릭 트래킹 (url 파라미터가 있으면)
 * 
 * 배포 방법:
 *   기존 Apps Script 프로젝트에서 이 코드로 교체 후
 *   배포 > 배포 관리 > 새 버전으로 업데이트
 * 
 * [피드백] 파라미터:
 *   vote     - 'up' 또는 'down'
 *   edition  - 에디션 번호 (예: '021')
 *   lang     - 언어 (ko, en, ja)
 *   member   - Ghost member UUID (선택)
 * 
 * [클릭 트래킹] 파라미터:
 *   url      - 이동할 원본 URL
 *   edition  - 에디션 번호
 *   section  - 섹션 이름 (calendar, briefing, trailer 등)
 *   label    - 클릭 항목명
 *   lang     - 언어
 */

function doGet(e) {
  // 라우팅: url 파라미터가 있으면 클릭 트래킹, vote가 있으면 피드백
  var url = e.parameter.url || '';
  var vote = e.parameter.vote || '';

  if (url) {
    return handleClickTrack(e);
  } else if (vote) {
    return handleFeedback(e);
  } else {
    return HtmlService.createHtmlOutput('<h2>잘못된 요청입니다.</h2>');
  }
}


// ════════════════════════════════════════════
//  클릭 트래킹 핸들러
// ════════════════════════════════════════════

function handleClickTrack(e) {
  var edition = e.parameter.edition || '';
  var section = e.parameter.section || '';
  var label   = e.parameter.label || '';
  var lang    = e.parameter.lang || 'ko';
  var url     = e.parameter.url || '';

  // URL 검증
  if (!url || (url.indexOf('http://') !== 0 && url.indexOf('https://') !== 0)) {
    return HtmlService.createHtmlOutput(
      '<html><body style="font-family:Inter,sans-serif;text-align:center;padding:60px">' +
      '<h2>⚠️ Invalid URL</h2></body></html>'
    );
  }

  // Google Sheet에 클릭 로그 기록
  try {
    var ss    = SpreadsheetApp.getActiveSpreadsheet();
    var sheet = ss.getSheetByName('ClickLog');
    if (!sheet) {
      sheet = ss.insertSheet('ClickLog');
      sheet.appendRow(['Timestamp', 'Edition', 'Section', 'Label', 'Language', 'URL']);
      sheet.getRange(1, 1, 1, 6).setFontWeight('bold');
      sheet.setFrozenRows(1);
    }
    // 최신 클릭이 위로 오도록 2행에 삽입
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

  // XSS 방지 이스케이프
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

  // 리다이렉트 HTML
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

  return HtmlService.createHtmlOutput(html)
    .setTitle('GTPlayer — Redirecting');
}


// ════════════════════════════════════════════
//  피드백 핸들러 (기존 기능)
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

    // 클라우드플레어가 넘겨주는 위치 정보 수신
    var countryStr = e.parameter.country || 'N/A';
    var cityStr = e.parameter.city || 'N/A';

    // 최신 투표가 위로 오도록 2행에 삽입
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

    var targetRow = 2;

    // 감사 페이지 HTML
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
    </div>
    
    <script>
      // 위치 추적은 앞단의 클라우드플레어 서버(Worker)에서 이미 완벽하게 수행하기 때문에
      // 브라우저에서 느리게 작동하는 부차적 위치 추적은 제거했습니다. 페이지를 닫으셔도 됩니다.
    </script>
    </body></html>`;
    
    return HtmlService.createHtmlOutput(html)
      .setTitle('GTPlayer Feedback');
      
  } catch (err) {
    return HtmlService.createHtmlOutput('<h2>오류: ' + err.toString() + '</h2>');
  }
}


// ════════════════════════════════════════════
//  유틸리티 함수
// ════════════════════════════════════════════

// 피드백 국가/도시 업데이트 (클라이언트 사이드 호출)
function updateLocation(row, country, city) {
  try {
    var ss = SpreadsheetApp.getActiveSpreadsheet();
    var sheet = ss.getSheetByName('Feedback');
    sheet.getRange(row, 6).setValue(country);
    sheet.getRange(row, 7).setValue(city);
  } catch(e) {}
}
