!macro preInit
  DetailPrint "Stopping running sql-guard processes before install..."
  nsExec::ExecToLog 'taskkill /F /T /IM "sql-guard.exe"'
  nsExec::ExecToLog 'taskkill /F /T /IM "sql-guard*.exe"'
  Sleep 1200
!macroend

!macro customUnInstall
  DetailPrint "Stopping running sql-guard processes before uninstall..."
  nsExec::ExecToLog 'taskkill /F /T /IM "sql-guard.exe"'
  nsExec::ExecToLog 'taskkill /F /T /IM "sql-guard*.exe"'
  Sleep 1200
!macroend
