!macro KillSqlGuardProcesses
  DetailPrint "Stopping running sql-guard processes..."
  ExecWait '$SYSDIR\\taskkill.exe /F /T /IM sql-guard.exe' $0
  DetailPrint "taskkill exit code: $0"
  Sleep 1500
!macroend

!macro preInit
  DetailPrint "Stopping running sql-guard processes before install..."
  !insertmacro KillSqlGuardProcesses
!macroend

!macro customUnInstall
  DetailPrint "Stopping running sql-guard processes before uninstall..."
  !insertmacro KillSqlGuardProcesses
!macroend
