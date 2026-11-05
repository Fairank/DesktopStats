// Fixed, read-only ASUS CPU cache bridge. No setters, monitoring startup,
// refresh, elevation, installation, arbitrary output path or command service.
using System;
using System.ComponentModel;
using System.Globalization;
using System.IO;
using System.IO.MemoryMappedFiles;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Runtime.Versioning;
using System.Security.AccessControl;
using System.Security.Principal;
using System.Text;
using System.Threading;

[assembly: TargetFramework(".NETFramework,Version=v4.7.2")]

internal static class AsusCpuTemperatureBridge
{
    internal const uint Magic = 0x54435344;
    internal const uint SensorId = 100859922; // 0x06030012, exact ASUS "CPU" channel.
    private const string SensorName = "CPU";
    private const string SensorClsid = "2627F8BE-4482-4081-BC62-8A12CA24BDF8";
    private const int Capacity = 64;
    private const uint ProcessQueryLimitedInformation = 0x1000;
    private const uint Synchronize = 0x100000;
    private const uint WaitTimeout = 258;
    private const uint Infinite = 0xffffffff;
    private const long UnixEpochTicks = 621355968000000000L;

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern IntPtr OpenProcess(uint access, bool inheritHandle, uint processId);
    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool CloseHandle(IntPtr handle);
    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern uint WaitForSingleObject(IntPtr handle, uint milliseconds);
    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool GetProcessTimes(IntPtr process, out long created, out long exited,
        out long kernel, out long user);
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern bool QueryFullProcessImageName(IntPtr process, uint flags,
        StringBuilder name, ref int size);
    [DllImport("advapi32.dll", SetLastError = true)]
    private static extern bool OpenProcessToken(IntPtr process, uint access, out IntPtr token);
    [DllImport("kernel32.dll")]
    private static extern uint GetCurrentProcessId();
    [DllImport("advapi32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern IntPtr OpenSCManager(string machine, string database, uint access);
    [DllImport("advapi32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern IntPtr OpenService(IntPtr manager, string service, uint access);
    [DllImport("advapi32.dll", SetLastError = true)]
    private static extern bool QueryServiceStatusEx(IntPtr service, int level,
        out ServiceStatusProcess status, uint size, out uint needed);
    [DllImport("advapi32.dll", SetLastError = true)]
    private static extern bool CloseServiceHandle(IntPtr service);

    [StructLayout(LayoutKind.Sequential)]
    private struct ServiceStatusProcess
    {
        internal uint ServiceType, CurrentState, ControlsAccepted, Win32ExitCode,
            ServiceSpecificExitCode, CheckPoint, WaitHint, ProcessId, ServiceFlags;
    }

    private sealed class BoundApplication : IDisposable
    {
        internal readonly IntPtr Handle;
        internal readonly uint Pid;
        private readonly long startTime;

        internal BoundApplication(uint pid, SecurityIdentifier user)
        {
            Pid = pid;
            Handle = OpenProcess(ProcessQueryLimitedInformation | Synchronize, false, pid);
            if (Handle == IntPtr.Zero) throw new Win32Exception(Marshal.GetLastWin32Error());
            try
            {
                startTime = GetProcessStartTime(Handle);
                var image = new StringBuilder(32768);
                int length = image.Capacity;
                if (!QueryFullProcessImageName(Handle, 0, image, ref length))
                    throw new Win32Exception(Marshal.GetLastWin32Error());
                string expected = Path.GetFullPath(Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                    @"Programs\DesktopStats\DesktopStats.exe"));
                if (!String.Equals(Path.GetFullPath(image.ToString()), expected,
                    StringComparison.OrdinalIgnoreCase))
                    throw new InvalidOperationException("Only the installed Desktop Stats process is accepted.");
                IntPtr token;
                if (!OpenProcessToken(Handle, 8, out token))
                    throw new Win32Exception(Marshal.GetLastWin32Error());
                try
                {
                    using (var identity = new WindowsIdentity(token))
                    {
                        if (identity.User == null || !identity.User.Equals(user))
                            throw new InvalidOperationException("The application must belong to this user.");
                    }
                }
                finally { CloseHandle(token); }
                if (!Alive()) throw new InvalidOperationException("The application has exited.");
            }
            catch { CloseHandle(Handle); throw; }
        }

        private static long GetProcessStartTime(IntPtr process)
        {
            long created, exited, kernel, user;
            if (!GetProcessTimes(process, out created, out exited, out kernel, out user))
                throw new Win32Exception(Marshal.GetLastWin32Error());
            return created;
        }

        internal bool Alive()
        {
            // Retaining this kernel object prevents PID reuse from rebinding it.
            return WaitForSingleObject(Handle, 0) == WaitTimeout
                && GetProcessStartTime(Handle) == startTime;
        }

        public void Dispose() { CloseHandle(Handle); }
    }

    private sealed class ProtocolWriter
    {
        private readonly MemoryMappedViewAccessor view;
        private readonly uint helperPid, appPid;
        private readonly object gate = new object();
        private uint sequence;
        private bool closed;

        internal ProtocolWriter(MemoryMappedViewAccessor value, uint helper, uint app)
        { view = value; helperPid = helper; appPid = app; }

        internal void Publish(uint state, uint raw, int hresult, long observed)
        {
            lock (gate)
            {
                if (closed) return;
                if (state == 3) closed = true;
                sequence = unchecked((sequence + 1) | 1U);
                view.Write(8, sequence);
                Thread.MemoryBarrier();
                view.Write(0, Magic);
                view.Write(4, 1U);
                view.Write(12, state);
                view.Write(16, helperPid);
                view.Write(20, SensorId);
                view.Write(24, state == 1 ? raw : 0U);
                view.Write(28, hresult);
                view.Write(32, state == 1 ? observed : 0L);
                view.Write(40, appPid);
                for (int offset = 44; offset < Capacity; offset += 4) view.Write(offset, 0U);
                Thread.MemoryBarrier();
                sequence = unchecked(sequence + 1);
                view.Write(8, sequence);
            }
        }

        internal void Close() { Publish(3, 0, 0, 0); }
    }

    private sealed class AsusCpuCache : IDisposable
    {
        private object server;
        private int sensorIndex = -1;
        private readonly ICpuProperties properties;

        // This injected seam contains getters only. Synthetic tests cannot
        // activate COM, inspect services or issue a monitoring/control method.
        private interface ICpuProperties
        {
            object Connect();
            object Sensors(object value);
            object Count(object value);
            object Item(object value, int index);
            object Id(object value);
            object Name(object value);
            object Current(object value);
            void Release(object value);
        }

        private sealed class ComProperties : ICpuProperties
        {
            public object Connect()
            {
                RequireExistingService();
                return Activator.CreateInstance(Type.GetTypeFromCLSID(new Guid(SensorClsid), true));
            }
            public object Sensors(object value) { return Get(value, "Sensors"); }
            public object Count(object value) { return Get(value, "Count"); }
            public object Item(object value, int index) { return Get(value, "Item", index); }
            public object Id(object value) { return Get(value, "id"); }
            public object Name(object value) { return Get(value, "name"); }
            public object Current(object value) { return Get(value, "current"); }
            public void Release(object value)
            {
                if (value != null && Marshal.IsComObject(value)) Marshal.ReleaseComObject(value);
            }
        }

        private static void RequireExistingService()
        {
            // Query only. Never let COM activation start a service the user
            // stopped: check the exact installed ASUS service before activation.
            // No StartService, service changes or process enumeration occur.
            IntPtr manager = OpenSCManager(null, null, 1); // SC_MANAGER_CONNECT
            if (manager == IntPtr.Zero) throw new Win32Exception(Marshal.GetLastWin32Error());
            try
            {
                IntPtr service = OpenService(manager, "asComSvc", 4); // SERVICE_QUERY_STATUS
                if (service == IntPtr.Zero) throw new Win32Exception(Marshal.GetLastWin32Error());
                try
                {
                    ServiceStatusProcess status;
                    uint needed;
                    if (!QueryServiceStatusEx(service, 0, out status,
                        (uint)Marshal.SizeOf(typeof(ServiceStatusProcess)), out needed))
                        throw new Win32Exception(Marshal.GetLastWin32Error());
                    if (status.CurrentState != 4) // SERVICE_RUNNING
                        throw new Win32Exception(1062); // ERROR_SERVICE_NOT_ACTIVE
                }
                finally { CloseServiceHandle(service); }
            }
            finally { CloseServiceHandle(manager); }
        }

        private static object Get(object value, string property, params object[] arguments)
        {
            // This private call site uses only literal PROPERTYGET names below.
            return value.GetType().InvokeMember(property, BindingFlags.GetProperty,
                null, value, arguments, CultureInfo.InvariantCulture);
        }

        private static uint Unsigned(object value)
        {
            if (!(value is uint)) throw new InvalidDataException("Expected ASUS VT_UI4.");
            return (uint)value;
        }

        internal AsusCpuCache() : this(new ComProperties()) { }

        private AsusCpuCache(ICpuProperties source)
        {
            properties = source;
            try
            {
                server = properties.Connect();
                object collection = null;
                try
                {
                    collection = properties.Sensors(server);
                    object countValue = properties.Count(collection);
                    if (!(countValue is int) && !(countValue is uint))
                        throw new InvalidDataException("Expected a bounded sensor count.");
                    long count = Convert.ToInt64(countValue, CultureInfo.InvariantCulture);
                    // Discovery is bounded and happens once per connection.
                    if (count < 0 || count > 64) throw new InvalidDataException("Sensor count exceeds the reviewed bound.");
                    for (int index = 0; index < count; index++)
                    {
                        object item = properties.Item(collection, index);
                        try
                        {
                            uint id = Unsigned(properties.Id(item));
                            string name = properties.Name(item) as string;
                            if (id == SensorId && String.Equals(name, SensorName, StringComparison.Ordinal))
                            {
                                if (sensorIndex >= 0) throw new InvalidDataException("The fixed CPU sensor is not unique.");
                                sensorIndex = index;
                            }
                        }
                        finally { properties.Release(item); }
                    }
                    if (sensorIndex < 0) throw new InvalidDataException("The fixed CPU sensor is absent.");
                }
                finally { properties.Release(collection); }
            }
            catch { Dispose(); throw; }
        }

        internal uint ReadRaw()
        {
            if (server == null) throw new ObjectDisposedException("AsusCpuCache");
            object collection = null, item = null;
            try
            {
                // Sensors is the vendor's snapshot boundary. Retaining only an
                // ISensor can keep returning a previous client snapshot even
                // while another COM client observes changing hardware values.
                collection = properties.Sensors(server);
                item = properties.Item(collection, sensorIndex);
                if (Unsigned(properties.Id(item)) != SensorId
                    || !String.Equals(properties.Name(item) as string, SensorName, StringComparison.Ordinal))
                    throw new InvalidDataException("The fixed CPU sensor identity changed.");
                return Unsigned(properties.Current(item));
            }
            finally
            {
                try { properties.Release(item); }
                finally { properties.Release(collection); }
            }
        }

        public void Dispose()
        {
            object previousServer = server;
            server = null;
            sensorIndex = -1;
            properties.Release(previousServer);
        }

        private sealed class FakeHandle
        {
            internal string Kind;
            internal int Generation, Index;
            internal bool Released;
        }

        private sealed class FakeProperties : ICpuProperties
        {
            internal string Fault;
            internal int Connections, SensorReads, CountReads, ItemReads, CurrentReads;
            internal int Live, Transient, ServerReleases;
            private FakeHandle New(string kind, int generation, int index)
            {
                Live++;
                if (kind != "server") Transient++;
                return new FakeHandle { Kind = kind, Generation = generation, Index = index };
            }
            private FakeHandle Handle(object value, string kind)
            {
                var handle = value as FakeHandle;
                Require(handle != null && handle.Kind == kind && !handle.Released);
                return handle;
            }
            private void Fail(string operation)
            {
                if (Fault == operation) throw new COMException("Synthetic " + operation, unchecked((int)0x80004005));
            }
            public object Connect() { Connections++; return New("server", 0, 0); }
            public object Sensors(object value)
            {
                Handle(value, "server"); Fail("Sensors");
                return New("collection", ++SensorReads, 0);
            }
            public object Count(object value)
            {
                Handle(value, "collection"); CountReads++;
                if (Fault == "count") return 65;
                return Fault == "duplicate" ? 3 : 2;
            }
            public object Item(object value, int index)
            {
                var collection = Handle(value, "collection"); Fail("Item"); ItemReads++;
                return New("item", collection.Generation, index);
            }
            public object Id(object value)
            {
                var item = Handle(value, "item"); Fail("id");
                if (Fault == "id_type") return (long)SensorId;
                return item.Index > 0 && Fault != "wrong_id" && Fault != "absent" ? SensorId : SensorId + 3U;
            }
            public object Name(object value)
            {
                var item = Handle(value, "item"); Fail("name");
                return item.Index > 0 && Fault != "wrong_name" ? SensorName : "CPU Package";
            }
            public object Current(object value)
            {
                var item = Handle(value, "item"); CurrentReads++; Fail("current");
                if (Fault == "raw_signed") return 500;
                if (Fault == "raw_double") return 50.0;
                if (Fault == "raw_unit") return "50 C";
                return (uint)(300 + item.Generation);
            }
            public void Release(object value)
            {
                if (value == null) return;
                var handle = (FakeHandle)value;
                Require(!handle.Released);
                handle.Released = true; Live--;
                if (handle.Kind == "server") ServerReleases++; else Transient--;
                if (handle.Kind == "item") Fail("release_item");
            }
        }

        internal static void TestFreshSnapshots()
        {
            var fake = new FakeProperties();
            var cache = new AsusCpuCache(fake);
            Require(fake.Connections == 1 && fake.SensorReads == 1 && fake.CountReads == 1
                && fake.ItemReads == 2 && fake.Transient == 0 && fake.Live == 1);
            Require(cache.ReadRaw() == 302U && cache.ReadRaw() == 303U);
            Require(fake.Connections == 1 && fake.SensorReads == 3 && fake.CountReads == 1
                && fake.ItemReads == 4 && fake.CurrentReads == 2 && fake.Transient == 0);
            cache.Dispose(); cache.Dispose();
            Require(fake.Live == 0 && fake.ServerReleases == 1);
            bool closed = false;
            try { cache.ReadRaw(); } catch (ObjectDisposedException) { closed = true; }
            Require(closed && fake.SensorReads == 3);
            foreach (string fault in new[] { "wrong_id", "wrong_name", "id_type", "raw_signed",
                "raw_double", "raw_unit", "Sensors", "Item", "id", "name", "current", "release_item" })
            {
                fake = new FakeProperties();
                cache = new AsusCpuCache(fake);
                fake.Fault = fault;
                bool failed = false;
                try { cache.ReadRaw(); }
                catch (InvalidDataException) { failed = true; }
                catch (COMException) { failed = true; }
                Require(failed && fake.Transient == 0 && fake.Live == 1);
                fake.Fault = null;
                Require(cache.ReadRaw() >= 302U && fake.Transient == 0);
                cache.Dispose();
                Require(fake.Live == 0 && fake.ServerReleases == 1);
            }
            foreach (string fault in new[] { "count", "absent", "duplicate", "Item", "id", "name" })
            {
                fake = new FakeProperties { Fault = fault };
                bool failed = false;
                try { new AsusCpuCache(fake); }
                catch (InvalidDataException) { failed = true; }
                catch (COMException) { failed = true; }
                Require(failed && fake.Live == 0 && fake.Transient == 0 && fake.ServerReleases == 1);
            }
        }
    }

    private static int HResult(Exception error)
    {
        while (error is TargetInvocationException && error.InnerException != null)
            error = error.InnerException;
        var native = error as Win32Exception;
        return native == null ? error.HResult : unchecked((int)(0x80070000U | (uint)native.NativeErrorCode));
    }

    private static MemoryMappedFile CreateMap(string name, SecurityIdentifier user)
    {
        var administrators = new SecurityIdentifier(WellKnownSidType.BuiltinAdministratorsSid, null);
        var security = new MemoryMappedFileSecurity();
        security.SetAccessRuleProtection(true, false);
        // Making Administrators the owner also prevents the unelevated user's
        // implicit owner WRITE_DAC right from bypassing the read-only user ACE.
        security.SetOwner(administrators);
        security.AddAccessRule(new AccessRule<MemoryMappedFileRights>(user,
            MemoryMappedFileRights.Read, AccessControlType.Allow));
        security.AddAccessRule(new AccessRule<MemoryMappedFileRights>(administrators,
            MemoryMappedFileRights.FullControl, AccessControlType.Allow));
        return MemoryMappedFile.CreateNew(name, Capacity, MemoryMappedFileAccess.ReadWrite,
            MemoryMappedFileOptions.None, security, HandleInheritability.None);
    }

    private static int Run(uint appPid)
    {
        using (WindowsIdentity identity = WindowsIdentity.GetCurrent())
        {
            if (identity.User == null || !new WindowsPrincipal(identity).IsInRole(WindowsBuiltInRole.Administrator))
                throw new UnauthorizedAccessException("An explicitly elevated launch is required; no elevation is requested here.");
            using (var app = new BoundApplication(appPid, identity.User))
            using (var map = CreateMap(@"Local\DesktopStats.CpuTemperature." + identity.User.Value + "." + appPid,
                identity.User))
            using (var view = map.CreateViewAccessor(0, Capacity, MemoryMappedFileAccess.ReadWrite))
            {
                var writer = new ProtocolWriter(view, GetCurrentProcessId(), appPid);
                writer.Publish(0, 0, 0, 0);
                // One blocked wait, no process enumeration or periodic extra
                // work. Even a stuck ASUS call cannot outlive the owning app.
                var exitWatcher = new Thread(delegate()
                {
                    if (WaitForSingleObject(app.Handle, Infinite) == 0)
                    {
                        try { writer.Close(); } catch (ObjectDisposedException) { }
                        Environment.Exit(0);
                    }
                });
                exitWatcher.IsBackground = true;
                exitWatcher.Name = "DesktopStats owner exit";
                exitWatcher.Start();
                AsusCpuCache cache = null;
                var clock = System.Diagnostics.Stopwatch.StartNew();
                long retryAt = 0;
                try
                {
                    while (app.Alive())
                    {
                        if (clock.ElapsedMilliseconds >= retryAt)
                        {
                            try
                            {
                                if (cache == null) cache = new AsusCpuCache();
                                uint raw = cache.ReadRaw();
                                long observed = (DateTime.UtcNow.Ticks - UnixEpochTicks) / TimeSpan.TicksPerMillisecond;
                                writer.Publish(1, raw, 0, observed);
                            }
                            catch (Exception error)
                            {
                                writer.Publish(2, 0, HResult(error), 0);
                                try { if (cache != null) cache.Dispose(); }
                                catch { }
                                cache = null;
                                retryAt = clock.ElapsedMilliseconds + 60000;
                            }
                        }
                        if (WaitForSingleObject(app.Handle, 2000) != WaitTimeout) break;
                    }
                }
                finally
                {
                    writer.Close();
                    if (cache != null) cache.Dispose();
                }
            }
        }
        return 0;
    }

    private static void Require(bool condition)
    { if (!condition) throw new InvalidDataException("Synthetic protocol self-test failed."); }

    private static int SelfTest()
    {
        // Anonymous synthetic memory only: no identity/target process lookup,
        // named IPC, COM activation, hardware access or administrator requirement.
        using (var map = MemoryMappedFile.CreateNew(null, Capacity))
        using (var view = map.CreateViewAccessor(0, Capacity))
        {
            var writer = new ProtocolWriter(view, 1234, 5678);
            writer.Publish(0, 999, 0, 123);
            Require(view.ReadUInt32(0) == Magic && view.ReadUInt32(4) == 1);
            Require(view.ReadUInt32(8) == 2 && view.ReadUInt32(12) == 0);
            Require(view.ReadUInt32(16) == 1234 && view.ReadUInt32(20) == SensorId);
            Require(view.ReadUInt32(24) == 0 && view.ReadInt64(32) == 0 && view.ReadUInt32(40) == 5678);
            writer.Publish(1, 500, 0, 1234567890123L);
            Require(view.ReadUInt32(8) == 4 && view.ReadUInt32(12) == 1);
            Require(view.ReadUInt32(24) == 500 && view.ReadInt64(32) == 1234567890123L);
            writer.Publish(2, 500, unchecked((int)0x80070005), 1234567890123L);
            Require(view.ReadUInt32(8) == 6 && view.ReadUInt32(12) == 2);
            Require(view.ReadUInt32(24) == 0 && view.ReadInt64(32) == 0);
            Require(view.ReadInt32(28) == unchecked((int)0x80070005));
            for (int offset = 44; offset < Capacity; offset += 4) Require(view.ReadUInt32(offset) == 0);
            writer.Close();
            Require(view.ReadUInt32(8) == 8 && view.ReadUInt32(12) == 3);
            writer.Publish(1, 600, 0, 1234567890124L);
            Require(view.ReadUInt32(8) == 8 && view.ReadUInt32(12) == 3 && view.ReadUInt32(24) == 0);
        }
        AsusCpuCache.TestFreshSnapshots();
        Console.WriteLine("CPU temperature bridge synthetic protocol and fresh-snapshot self-tests passed.");
        return 0;
    }

    [MTAThread]
    private static int Main(string[] args)
    {
        try
        {
            if (!BitConverter.IsLittleEndian) return 2;
            if (args.Length == 1 && args[0] == "--self-test") return SelfTest();
            uint pid;
            if (args.Length != 2 || args[0] != "--app-pid"
                || !UInt32.TryParse(args[1], NumberStyles.None, CultureInfo.InvariantCulture, out pid)
                || pid == 0 || pid > Int32.MaxValue || pid == GetCurrentProcessId()) return 2;
            return Run(pid);
        }
        catch (Exception error)
        {
            Console.Error.WriteLine("CPU temperature bridge refused or stopped: HRESULT 0x" + HResult(error).ToString("X8"));
            return 1;
        }
    }
}
