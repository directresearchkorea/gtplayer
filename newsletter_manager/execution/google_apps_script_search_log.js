/**
 * Google Apps Script — Ghost 검색어 수집기
 * 
 * 사용법:
 * 1. Google Sheets를 새로 만든다
 * 2. 확장 프로그램 > Apps Script 클릭
 * 3. 이 코드를 붙여넣고 저장
 * 4. 배포 > 새 배포 > 유형: 웹 앱 > 액세스: 모든 사용자 > 배포
 * 5. 생성된 URL을 Ghost 테마의 SEARCH_LOG_URL에 붙여넣기
 */

function doPost(e) {
  try {
    var data = JSON.parse(e.postData.contents);
    var sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
    
    // 헤더가 없으면 추가
    if (sheet.getLastRow() === 0) {
      sheet.appendRow(['Timestamp', 'Search Query', 'Results Count', 'Language', 'Country', 'City', 'User Agent']);
    }
    
    // 헤더 바로 아래(2행)에 삽입 → 최신 기록이 항상 맨 위
    sheet.insertRowAfter(1);
    sheet.getRange(2, 1, 1, 7).setValues([[
      Utilities.formatDate(new Date(), "Asia/Seoul", "yyyy-MM-dd HH:mm:ss"),
      data.query ? "'" + data.query : '',
      data.resultsCount || 0,
      data.language || 'unknown',
      data.country || 'unknown',
      data.city || 'unknown',
      data.userAgent || ''
    ]]);
    
    return ContentService
      .createTextOutput(JSON.stringify({ status: 'ok' }))
      .setMimeType(ContentService.MimeType.JSON);
      
  } catch (err) {
    return ContentService
      .createTextOutput(JSON.stringify({ status: 'error', message: err.toString() }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

// GET 요청으로 테스트할 때 사용 (선수)
function doGet(e) {
  return ContentService
    .createTextOutput(JSON.stringify({ status: 'ready', message: 'Search log endpoint is active.' }))
    .setMimeType(ContentService.MimeType.JSON);
}
