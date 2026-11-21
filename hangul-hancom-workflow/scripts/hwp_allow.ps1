# 한컴 자동화 보안 창('...파일에 접근하려는 시도')이 뜨면 '모두 허용'을 UI 자동화로 누른다.
# 마우스·키보드를 쓰지 않으므로 사용자가 다른 창(다른 데스크톱)에서 일해도 방해하지 않는다.
param([int]$Seconds = 120)
Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes
Add-Type @"
using System; using System.Text; using System.Collections.Generic; using System.Runtime.InteropServices;
public class HW {
  delegate bool EnumProc(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc f, IntPtr l);
  [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr h, uint m, IntPtr w, IntPtr l);
  [StructLayout(LayoutKind.Sequential)] public struct POINT { public int X; public int Y; }
  [DllImport("user32.dll")] public static extern bool ScreenToClient(IntPtr h, ref POINT p);
  [DllImport("user32.dll")] static extern bool GetCursorPos(out POINT p);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L; public int T; public int R; public int B; }
  [DllImport("user32.dll")] static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] static extern bool SetWindowPos(IntPtr h, IntPtr after, int x, int y, int cx, int cy, uint flags);
  // WPF는 실제 마우스가 그 창 위에 있을 때만 보낸 클릭을 받아들인다(11-11 확인).
  // 마우스를 옮기지 않고, 창을 옮겨 단추가 마우스 아래에 오게 한 뒤 누른다. 활성화하지 않는다(SWP_NOACTIVATE).
  public static void ClickUnderCursor(IntPtr h, int sx, int sy) {
    RECT r; GetWindowRect(h, out r); POINT c; GetCursorPos(out c);
    SetWindowPos(h, (IntPtr)(-1), c.X - (sx - r.L), c.Y - (sy - r.T), 0, 0, 0x0001 | 0x0010);
    System.Threading.Thread.Sleep(400);
    GetCursorPos(out c); Click(h, c.X, c.Y);
  }
  // WPF 버튼은 UIA Invoke가 듣지 않으므로, 그 창에만 마우스 메시지를 보낸다(실제 마우스는 움직이지 않음)
  public static void Click(IntPtr h, int sx, int sy) {
    var p = new POINT { X = sx, Y = sy }; ScreenToClient(h, ref p);
    var l = (IntPtr)((p.Y << 16) | (p.X & 0xFFFF));
    PostMessage(h, 0x0200, IntPtr.Zero, l); PostMessage(h, 0x0201, (IntPtr)1, l);
    System.Threading.Thread.Sleep(60); PostMessage(h, 0x0202, IntPtr.Zero, l);
  }
  public static List<IntPtr> Windows(uint[] pids) {
    var r = new List<IntPtr>();
    EnumWindows((h, l) => { uint p; GetWindowThreadProcessId(h, out p); if (Array.IndexOf(pids, p) >= 0 && IsWindowVisible(h)) r.Add(h); return true; }, IntPtr.Zero);
    return r;
  }
}
"@
$end = (Get-Date).AddSeconds($Seconds)
while ((Get-Date) -lt $end) {
  $pids = [uint32[]]@(Get-Process Hwp -ErrorAction SilentlyContinue | ForEach-Object { $_.Id })
  if ($pids.Count) {
    foreach ($h in [HW]::Windows($pids)) {
      try {
        $el = [System.Windows.Automation.AutomationElement]::FromHandle($h)
        $msg = $el.FindFirst([System.Windows.Automation.TreeScope]::Descendants,
          (New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::AutomationIdProperty, 'PART_Message')))
        if ($msg -and $msg.Current.Name -like '*접근하려는 시도*') {
          $btns = $el.FindAll([System.Windows.Automation.TreeScope]::Descendants,
            (New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ControlTypeProperty, [System.Windows.Automation.ControlType]::Button)))
          $b = $btns | Where-Object { $_.Current.Name -like '모두 허용*' } | Select-Object -First 1
          if ($b) { $r = $b.Current.BoundingRectangle; [HW]::ClickUnderCursor($h, [int]($r.X + $r.Width / 2), [int]($r.Y + $r.Height / 2)); Start-Sleep -Milliseconds 1200 }
        }
      } catch {}
    }
  }
  Start-Sleep -Milliseconds 300
}
