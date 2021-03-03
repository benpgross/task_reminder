
/*
This script automatically adds a timestamp when someone begins
editing any of the labelled columns in the google sheet. It only
does that update once while there is no text in the ID column.

The script is run by adding a script directly in sheets, but I 
have copied it here for reference.

The goal of the ID is for future iterations of the project to be
able to respond to the reminder text with the ID number to specify
which Chore you've completed - this is key since task will likely
have the same names. 

*/
function onEdit() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getActiveSheet();
  var date = new Date();
  var time_stamp = Math.floor((date.getTime()/1000)).toString(); 
  var cell = sheet.getActiveCell();
  var col = cell.getColumn();
  var row = cell.getRow();
  var offset = 5 - col;
  if (cell.offset(0,offset).isBlank() && offset != 0){
    cell.offset(0,offset).setValue(time_stamp);
  }
}