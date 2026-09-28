using System;
using System.Drawing;
using System.Runtime.InteropServices;
using System.Threading;
using System.Windows.Forms;

internal sealed class PresenceContext : ApplicationContext
{
    [StructLayout(LayoutKind.Sequential)]
    private struct LastInput
    {
        public uint Size;
        public uint Time;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct MouseInput
    {
        public int X;
        public int Y;
        public uint MouseData;
        public uint Flags;
        public uint Time;
        public UIntPtr ExtraInfo;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct Input
    {
        public uint Type;
        public MouseInput Mouse;
    }

    [DllImport("user32.dll", SetLastError = true)]
    private static extern uint SendInput(uint count, Input[] inputs, int size);

    [DllImport("user32.dll")]
    private static extern bool GetLastInputInfo(ref LastInput input);

    [DllImport("kernel32.dll")]
    private static extern uint SetThreadExecutionState(uint flags);

    private readonly NotifyIcon icon;
    private readonly Icon appIcon = Icon.ExtractAssociatedIcon(Application.ExecutablePath);
    private readonly ContextMenuStrip menu;
    private readonly ToolStripMenuItem toggle;
    private readonly System.Windows.Forms.Timer timer;
    private bool active;

    public PresenceContext()
    {
        menu = new ContextMenuStrip();
        toggle = new ToolStripMenuItem("Pause", null, delegate { SetActive(!active); });
        menu.Items.Add(toggle);
        menu.Items.Add("Exit", null, delegate { ExitThread(); });
        icon = new NotifyIcon();
        icon.ContextMenuStrip = menu;
        icon.Icon = SystemIcons.Application;
        icon.Visible = true;
        icon.DoubleClick += delegate { SetActive(!active); };
        timer = new System.Windows.Forms.Timer();
        timer.Interval = 15000;
        timer.Tick += Tick;
        SetActive(true);
        icon.ShowBalloonTip(4000, "Evergreen", "Staying green. Right-click this tray icon to pause or exit.", ToolTipIcon.Info);
    }

    private void SetActive(bool enabled)
    {
        if (enabled && SetThreadExecutionState(0x80000003) == 0)
        {
            icon.ShowBalloonTip(5000, "Unable to start", "Windows could not enable the keep-awake request.", ToolTipIcon.Warning);
            enabled = false;
        }
        active = enabled;
        if (!active)
            SetThreadExecutionState(0x80000000);
        timer.Enabled = active;
        toggle.Text = active ? "Pause" : "Resume";
        icon.Text = active ? "Evergreen - Running" : "Evergreen - Paused";
        icon.Icon = active ? appIcon : SystemIcons.Application;
    }

    private void Tick(object sender, EventArgs args)
    {
        LastInput last = new LastInput();
        last.Size = (uint)Marshal.SizeOf(typeof(LastInput));
        if (!GetLastInputInfo(ref last))
            return;
        uint idle = unchecked((uint)Environment.TickCount - last.Time);
        if (idle < 45000)
            return;
        Input[] inputs = new Input[2];
        inputs[0].Mouse.X = 1;
        inputs[0].Mouse.Flags = 0x0001;
        inputs[1].Mouse.X = -1;
        inputs[1].Mouse.Flags = 0x0001;
        uint sent = SendInput((uint)inputs.Length, inputs, Marshal.SizeOf(typeof(Input)));
        icon.Text = sent == 2
            ? "Evergreen - Running"
            : "Evergreen - Input blocked by Windows";
    }

    protected override void ExitThreadCore()
    {
        timer.Stop();
        SetThreadExecutionState(0x80000000);
        icon.Visible = false;
        timer.Dispose();
        icon.Dispose();
        menu.Dispose();
        appIcon.Dispose();
        base.ExitThreadCore();
    }

    [STAThread]
    private static void Main()
    {
        bool created;
        using (Mutex mutex = new Mutex(true, "Local\\Evergreen", out created))
        {
            if (!created)
            {
                MessageBox.Show("Evergreen is already running. Look in the system tray, including hidden icons.", "Evergreen");
                return;
            }
            try
            {
                Application.EnableVisualStyles();
                Application.SetCompatibleTextRenderingDefault(false);
                Application.Run(new PresenceContext());
            }
            finally
            {
                mutex.ReleaseMutex();
            }
        }
    }
}
