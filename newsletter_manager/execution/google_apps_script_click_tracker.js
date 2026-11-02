/**
 * Google Apps Script — 뉴스레터 클릭 트래커
 * 
 * 사용법:
 * 1. 기존 피드백 Google Sheets에서 확장 프로그램 > Apps Script 열기
 *    (또는 새 Google Sheets 생성)
 * 2. 새 스크립트 파일 추가 (+ 버튼) → 이 코드 붙여넣기
 * 3. 배포 > 새 배포 > 유형: 웹 앱 > 액세스: 모든 사용자 > 배포
 * 4. 생성된 URL을 publish_edition.py의 CLICK_TRACKER_URL에 붙여넣기
 * 
 * 파라미터:
 *   edition  - 에디션 번호 (예: '021')
 *   section  - 섹션 이름 (calendar, briefing, trailer 등)
 *   label    - 클릭한 항목명 (게임명, 기사 제목 등)
 *   lang     - 언어 (ko, en, ja)
 *   url      - 이동할 원본 URL
 * 
 * 시트 구조 (ClickLog):
 *   Timestamp | Edition | Section | Label | Language | URL
 */

function doGet(e) {
  var edition = e.parameter.edition || '';
  var section = e.parameter.section || '';
  var label   = e.parameter.label || '';
  var lang    = e.parameter.lang || 'ko';
  var url     = e.parameter.url || '';

  // 앞뒤 공백 제거 및 소문자 변환 후 검증 (대소문자 무관성)
  url = url.trim();
  var checkUrl = url.toLowerCase();
  if (!url || (checkUrl.indexOf('http://') !== 0 && checkUrl.indexOf('https://') !== 0 && checkUrl.indexOf('mailto:') !== 0)) {
    return HtmlService.createHtmlOutput(
      '<html><body style="font-family:sans-serif;text-align:center;padding:60px">' +
      '<h2>⚠️ Invalid URL</h2><p>' + url + '</p></body></html>'
    );
  }

  // ── Google Sheet에 클릭 로그 기록 (동시성 제어 적용) ──
  var lock = LockService.getScriptLock();
  try {
    // 여러 명이 동시에 클릭할 경우 순차적으로 처리되도록 최대 10초간 대기 (빈칸/덮어쓰기 방지)
    lock.waitLock(10000); 

    var ss    = SpreadsheetApp.getActiveSpreadsheet();
    var sheet = ss.getSheetByName('ClickLog');
    if (!sheet) {
      sheet = ss.insertSheet('ClickLog');
      sheet.appendRow(['Timestamp', 'Edition', 'Section', 'Label', 'Language', 'URL', 'IP Address', 'Country', 'City']);
      sheet.getRange(1, 1, 1, 9).setFontWeight('bold');
      sheet.setFrozenRows(1);
    }
    
    // IP 주소와 위치 정보 수신
    var ipStr = e.parameter.ip || 'N/A';
    var countryStr = e.parameter.country || 'N/A';
    var cityStr = e.parameter.city || 'N/A';

    // 최신 클릭이 위로 오도록 2행에 삽입
    sheet.insertRowAfter(1);
    sheet.getRange(2, 1, 1, 9).setValues([[
      Utilities.formatDate(new Date(), "Asia/Seoul", "yyyy-MM-dd HH:mm:ss"),
      edition,
      section,
      label,
      lang,
      url,
      ipStr,
      countryStr,
      cityStr
    ]]);
  } catch (err) {
    // 로깅 실패해도 리다이렉트는 수행
    Logger.log('Click logging error: ' + err.toString());
  } finally {
    lock.releaseLock();
  }

  // ── 리다이렉트 HTML 반환 ──
  // XSS 방지를 위한 이스케이프
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

  // 화면에 "Redirecting..." 텍스트를 표시하지 않고 눈에 띄지 않게(빈 하얀 화면) 처리하여
  // 로딩되는 느낌을 최소화합니다.
  var html = '<!DOCTYPE html><html><head>'
    + '<meta charset="UTF-8">'
    + '<meta http-equiv="refresh" content="0;url=' + safeUrl + '">'
    + '<script>window.location.replace("' + jsUrl + '");</script>'
    + '</head>'
    + '<body style="background:#ffffff;margin:0;padding:0;">'
    + '</body></html>';

  return HtmlService.createHtmlOutput(html)
    .setTitle('GTPlayer — Redirecting');
}
