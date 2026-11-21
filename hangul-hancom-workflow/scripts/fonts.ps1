# 사용자 글꼴(관리자 권한 없이)을 설치하거나, 이번 로그인에서 풀린 사용자 글꼴을 다시 올린다.
#   powershell -File fonts.ps1 -Install "C:\path\to\ttf폴더"   : *.ttf/*.otf를 %LOCALAPPDATA%\Microsoft\Windows\Fonts에 복사, HKCU 등록, 바로 사용
#   powershell -File fonts.ps1 -Reload                       : 사용자 글꼴 폴더의 글꼴을 이번 세션에 다시 올림(AddFontResource)
#   powershell -File fonts.ps1 -List "KoPub"                 : 지금 쓸 수 있는 글꼴 이름 가운데 일부를 보여 줌
# 사용자 글꼴은 다시 로그인하면 목록에서 빠져 있을 때가 있다(파일과 레지스트리는 남음). PDF를 만들기 전에 render.py의 글꼴 경고를 본다.
param([string]$Install = "", [switch]$Reload, [string]$List = "")
Add-Type @'
using System; using System.Runtime.InteropServices;
public class FontInst {
 [DllImport("gdi32.dll", CharSet = CharSet.Unicode)] public static extern int AddFontResourceW(string f);
 [DllImport("user32.dll", SetLastError = true)] public static extern IntPtr SendMessageTimeout(IntPtr h, uint m, IntPtr w, IntPtr l, uint flags, uint timeout, out IntPtr res);
 public static void Notify(){ IntPtr r; SendMessageTimeout((IntPtr)0xFFFF, 0x001D, IntPtr.Zero, IntPtr.Zero, 2, 3000, out r); } }
'@
$dst = Join-Path $env:LOCALAPPDATA "Microsoft\Windows\Fonts"
$reg = "HKCU:\Software\Microsoft\Windows NT\CurrentVersion\Fonts"
New-Item -ItemType Directory -Force $dst | Out-Null
if (-not (Test-Path $reg)) { New-Item -Path $reg -Force | Out-Null }
if ($Install) {
  foreach ($f in Get-ChildItem $Install -Include *.ttf, *.otf -Recurse) {
    $t = Join-Path $dst $f.Name
    if (-not (Test-Path $t)) { Copy-Item $f.FullName $t }
    $kind = if ($f.Extension -eq ".otf") { "OpenType" } else { "TrueType" }
    Set-ItemProperty -Path $reg -Name ("{0} ({1})" -f $f.BaseName, $kind) -Value $t
    "{0} -> {1}" -f $f.Name, [FontInst]::AddFontResourceW($t)
  }
  [FontInst]::Notify()
}
if ($Reload) {
  foreach ($f in Get-ChildItem $dst -Include *.ttf, *.otf, *.ttc -Recurse) { "{0} -> {1}" -f $f.Name, [FontInst]::AddFontResourceW($f.FullName) }
  [FontInst]::Notify()
}
if ($List) {
  Add-Type -AssemblyName System.Drawing
  (New-Object System.Drawing.Text.InstalledFontCollection).Families | Where-Object { $_.Name -like "*$List*" } | ForEach-Object { $_.Name }
}
