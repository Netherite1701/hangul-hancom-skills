# 열려 있는 '열기' 대화상자(#32770)의 파일 이름 칸에 경로를 넣고 '열기'를 누른다. 키보드·마우스 입력은 쓰지 않는다.
# 사용: powershell -File pick_file.ps1 -Path "C:\...\파일"
param([Parameter(Mandatory = $true)][string]$Path)
Add-Type @'
using System; using System.Text; using System.Runtime.InteropServices;
public class PickFile { public delegate bool CB(IntPtr h, IntPtr l);
 [DllImport("user32.dll")] public static extern bool EnumWindows(CB cb, IntPtr l);
 [DllImport("user32.dll")] public static extern bool EnumChildWindows(IntPtr p, CB cb, IntPtr l);
 [DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
 [DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern int GetClassName(IntPtr h, StringBuilder s, int n);
 [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
 [DllImport("user32.dll")] public static extern int GetDlgCtrlID(IntPtr h);
 [DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern IntPtr SendMessage(IntPtr h, uint m, IntPtr w, string l);
 [DllImport("user32.dll")] public static extern IntPtr SendMessage(IntPtr h, uint m, IntPtr w, IntPtr l);
 public static string Go(string path){ IntPtr dlg=IntPtr.Zero; EnumWindows((h,l)=>{ var c=new StringBuilder(64); GetClassName(h,c,64); var s=new StringBuilder(200); GetWindowText(h,s,200); if(IsWindowVisible(h) && c.ToString()=="#32770" && (s.ToString()=="열기"||s.ToString()=="Open")){ dlg=h; return false;} return true;}, IntPtr.Zero);
  if(dlg==IntPtr.Zero) return "no dialog";
  IntPtr edit=IntPtr.Zero, ok=IntPtr.Zero; EnumChildWindows(dlg,(ch,l)=>{ var c=new StringBuilder(64); GetClassName(ch,c,64); int id=GetDlgCtrlID(ch); if(c.ToString()=="Edit" && id==1148) edit=ch; if(c.ToString()=="Button" && id==1) ok=ch; return true;}, IntPtr.Zero);
  if(edit==IntPtr.Zero||ok==IntPtr.Zero) return "controls not found";
  SendMessage(edit, 0x000C, IntPtr.Zero, path); System.Threading.Thread.Sleep(300); SendMessage(ok, 0x00F5, IntPtr.Zero, IntPtr.Zero); return "sent to dialog "+dlg; } }
'@
if (-not (Test-Path -LiteralPath $Path)) { "file not found: $Path"; exit 1 }
$r = "no dialog"
for ($i = 0; $i -lt 20 -and $r -eq "no dialog"; $i++) { $r = [PickFile]::Go($Path); if ($r -eq "no dialog") { Start-Sleep -Milliseconds 500 } }
$r
