# Local look-dev only: one small frame of each named shot, then a contact sheet.
param([string[]]$Shots, [int]$Frames = 48, [string]$At = "24", [int]$Samples = 4, [string]$Res = "640x360")
$root = "D:\Stim Video Sample"
$blender = "$root\build\blender-4.5.9-windows-x64\blender.exe"
$dir = "$root\build\qa"
New-Item -ItemType Directory -Force $dir | Out-Null
foreach ($s in ($Shots -split ',')) {
  $out = "$dir\$s"
  Remove-Item "$out\*.jpg" -ErrorAction SilentlyContinue
  $t = Get-Date
  & $blender -b --factory-startup -P "$root\blender\render.py" -- --shot $s --frames $Frames --out $out --only $At --samples $Samples --res $Res *> "$dir\$s.log"
  $secs = [int]((Get-Date) - $t).TotalSeconds
  $err = Select-String -Path "$dir\$s.log" -Pattern 'Error:|Traceback|Exception' | Select-Object -First 3 | ForEach-Object { $_.Line }
  $n = (Get-ChildItem "$out\*.jpg" -ErrorAction SilentlyContinue | Measure-Object).Count
  "$s : $n frame(s), ${secs}s $err"
  if ($err) { Select-String -Path "$dir\$s.log" -Pattern 'line \d+, in|Error' | Select-Object -Last 5 | ForEach-Object { "   " + $_.Line.Trim() } }
}
