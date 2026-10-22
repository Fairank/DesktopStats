// SPDX-License-Identifier: MIT
// Original Desktop Stats collector. Upstream libraries keep their own licenses.
// No GUI, settings import, driver installation, elevation or hardware controls.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Runtime.CompilerServices;
using System.Text;
using System.Threading;
using System.Web.Script.Serialization;
using LibreHardwareMonitor.Hardware;

namespace DesktopStats.Collector
{
    internal sealed class HardwareRow
    {
        public string id;
        public string name;
        public string type;
        public string parent_id;
    }

    internal sealed class SensorRow
    {
        public string id;
        public string name;
        public string hardware_id;
        public string hardware_name;
        public string hardware_type;
        public string type;
        public string unit;
        public double? value;
        public double? min;
        public double? max;
    }

    internal sealed class Snapshot
    {
        public int schema = 1;
        public string provider = "LibreHardwareMonitor";
        public string version = "0.9.6";
        public double timestamp;
        public List<HardwareRow> hardware = new List<HardwareRow>();
        public List<SensorRow> sensors = new List<SensorRow>();
        public int skipped_types;
        public int update_errors;
        public int truncated;
    }

    internal sealed class Options
    {
        internal bool Once;
        internal bool SelfTest;
        internal double Interval = 1.0;
        internal double? Duration;
    }

    internal static class Program
    {
        private const int MaxSensors = 4096;
        private const int MaxHardware = 1024;
        private const int MaxDepth = 16;
        private const int MaxLineBytes = 2 * 1024 * 1024;
        private static readonly DateTime Epoch = new DateTime(1970, 1, 1, 0, 0, 0, DateTimeKind.Utc);
        private static readonly UTF8Encoding Utf8 = new UTF8Encoding(false);
        private static readonly ManualResetEvent Stop = new ManualResetEvent(false);

        private static int Main(string[] args)
        {
            Console.OutputEncoding = Utf8;
            Options options;
            try { options = ParseOptions(args); }
            catch (ArgumentException error)
            {
                Console.Error.WriteLine(error.Message);
                return 2;
            }

            // Keep this branch separate from RunHardware: self-test never constructs
            // Computer, invokes Open/Update/Close, reads devices or imports settings.
            if (options.SelfTest) return SelfTest();

            Console.CancelKeyPress += delegate(object sender, ConsoleCancelEventArgs e)
            {
                e.Cancel = true;
                Stop.Set();
            };

            try { return RunHardware(options); }
            catch (IOException) { return 0; } // Parent closed its output pipe.
            catch (Exception error)
            {
                Console.Error.WriteLine("collector failed: " + error.GetType().Name);
                return 1;
            }
        }

        private static Options ParseOptions(string[] args)
        {
            Options options = new Options();
            for (int i = 0; i < args.Length; i++)
            {
                string arg = args[i];
                if (arg == "--once") options.Once = true;
                else if (arg == "--self-test") options.SelfTest = true;
                else if (arg == "--interval" || arg == "--duration")
                {
                    double value;
                    if (++i >= args.Length || !double.TryParse(args[i], NumberStyles.Float,
                        CultureInfo.InvariantCulture, out value) || double.IsNaN(value) || double.IsInfinity(value))
                        throw new ArgumentException("Expected a finite number after " + arg + ".");
                    if (arg == "--interval")
                    {
                        if (value < 0.5 || value > 5.0)
                            throw new ArgumentException("Collector interval must be between 0.5 and 5 seconds.");
                        options.Interval = value;
                    }
                    else
                    {
                        if (value <= 0 || value > 86400)
                            throw new ArgumentException("Duration must be greater than zero and at most 86400 seconds.");
                        options.Duration = value;
                    }
                }
                else throw new ArgumentException("Unknown collector argument.");
            }
            return options;
        }

        [MethodImpl(MethodImplOptions.NoInlining)]
        private static int RunHardware(Options options)
        {
            // Do not accept settings from the desktop app or third-party GUI. The
            // stock empty settings leave fan ControlMode Undefined. Never invoke
            // ISensor.Control setters, even when a Control channel is discovered.
            Computer computer = new Computer
            {
                IsCpuEnabled = false,
                IsMotherboardEnabled = false,
                IsControllerEnabled = false,
                IsPsuEnabled = false,
                IsMemoryEnabled = false,
                IsPowerMonitorEnabled = false,
                IsGpuEnabled = true,
                IsStorageEnabled = true,
                IsNetworkEnabled = true,
                // Upstream 0.9.6 can retain stale status after battery-tag/query
                // failures. The main app's verified native Battery provider owns
                // this scope; keep the generic raw-mWh protocol for future engines.
                IsBatteryEnabled = false
            };

            if (!options.Once) StartInputWatcher();
            if (Stop.WaitOne(0)) return 0;
            Stopwatch elapsed = Stopwatch.StartNew();
            try
            {
                // Upstream 0.9.6 Open unconditionally allocates its CPUID/RDTSC
                // executable buffer. It does not install a driver. The disabled
                // groups above prevent its PawnIO/SMBus/controller paths here.
                computer.Open();
                do
                {
                    if (Stop.WaitOne(0) || (options.Duration.HasValue && elapsed.Elapsed.TotalSeconds >= options.Duration.Value))
                        break;
                    double start = elapsed.Elapsed.TotalSeconds;
                    Snapshot snapshot = Capture(computer);
                    Console.Out.WriteLine(SerializeBounded(snapshot));
                    Console.Out.Flush();
                    if (options.Once) break;

                    double wait = Math.Max(0, options.Interval - (elapsed.Elapsed.TotalSeconds - start));
                    if (options.Duration.HasValue)
                        wait = Math.Min(wait, Math.Max(0, options.Duration.Value - elapsed.Elapsed.TotalSeconds));
                    if (Stop.WaitOne((int)Math.Ceiling(wait * 1000))) break;
                } while (true);
                return 0;
            }
            finally
            {
                try { computer.Close(); }
                catch (Exception error) { Console.Error.WriteLine("collector close failed: " + error.GetType().Name); }
            }
        }

        private static void StartInputWatcher()
        {
            Thread reader = new Thread(delegate()
            {
                try
                {
                    string line;
                    while ((line = Console.In.ReadLine()) != null)
                    {
                        if (String.Equals(line.Trim(), "stop", StringComparison.OrdinalIgnoreCase)) break;
                        // No runtime commands can enable hardware groups or controls.
                    }
                }
                catch (IOException) { }
                finally { Stop.Set(); }
            });
            reader.IsBackground = true;
            reader.Name = "collector-parent-input";
            reader.Start();
        }

        [MethodImpl(MethodImplOptions.NoInlining)]
        private static Snapshot Capture(Computer computer)
        {
            Snapshot snapshot = new Snapshot();
            HashSet<string> visitedHardware = new HashSet<string>(StringComparer.Ordinal);
            HashSet<string> visitedSensors = new HashSet<string>(StringComparer.Ordinal);
            foreach (IHardware hardware in computer.Hardware)
                Visit(hardware, null, 0, snapshot, visitedHardware, visitedSensors);
            snapshot.timestamp = (DateTime.UtcNow - Epoch).TotalSeconds;
            return snapshot;
        }

        private static void Visit(IHardware hardware, string parentId, int depth, Snapshot snapshot,
            HashSet<string> visitedHardware, HashSet<string> visitedSensors)
        {
            if (depth > MaxDepth || snapshot.hardware.Count >= MaxHardware)
            {
                snapshot.truncated++;
                return;
            }
            string id = hardware.Identifier.ToString();
            if (!ValidId(id) || !visitedHardware.Add(id)) return;
            string name = SafeLabel(hardware.Name);
            string hardwareType = hardware.HardwareType.ToString();
            snapshot.hardware.Add(new HardwareRow { id = id, name = name, type = hardwareType, parent_id = parentId });
            bool updated = true;
            try { hardware.Update(); }
            catch (Exception) { updated = false; snapshot.update_errors++; }

            foreach (ISensor sensor in hardware.Sensors)
            {
                if (snapshot.sensors.Count >= MaxSensors) { snapshot.truncated++; break; }
                string type = sensor.SensorType.ToString();
                string unit;
                if (!TryUnit(type, out unit)) { snapshot.skipped_types++; continue; }
                string sensorId = sensor.Identifier.ToString();
                if (!ValidId(sensorId) || !visitedSensors.Add(sensorId)) continue;
                string rawName = sensor.Name;
                snapshot.sensors.Add(new SensorRow
                {
                    id = sensorId,
                    name = SafeLabel(rawName),
                    hardware_id = id,
                    hardware_name = name,
                    hardware_type = hardwareType,
                    type = type,
                    unit = unit,
                    value = updated ? SensorValue(hardwareType, type, rawName, sensor.Value) : null,
                    min = SensorValue(hardwareType, type, rawName, sensor.Min),
                    max = SensorValue(hardwareType, type, rawName, sensor.Max)
                });
            }

            foreach (IHardware child in hardware.SubHardware)
                Visit(child, id, depth + 1, snapshot, visitedHardware, visitedSensors);
        }

        private static bool TryUnit(string type, out string unit)
        {
            switch (type)
            {
                case "Temperature": unit = "°C"; return true;
                case "Fan": unit = "RPM"; return true;
                case "Voltage": unit = "V"; return true;
                case "Current": unit = "A"; return true;
                case "Power": unit = "W"; return true;
                case "Clock": unit = "MHz"; return true;
                case "Load":
                case "Level": unit = "%"; return true;
                case "Data": unit = "GB"; return true; // Upstream uses 2^30 bytes.
                case "SmallData": unit = "MB"; return true; // Upstream uses 2^20 bytes.
                case "Throughput": unit = "B/s"; return true;
                case "Factor": unit = ""; return true;
                case "Energy": unit = "mWh"; return true; // Raw; parent normalizes explicitly.
                default: unit = null; return false; // No Control/Noise guesses.
            }
        }

        private static double? Finite(float? value)
        {
            return value.HasValue && !float.IsNaN(value.Value) && !float.IsInfinity(value.Value)
                ? (double?)value.Value : null;
        }

        private static double? SensorValue(string hardwareType, string type, string rawName, float? value)
        {
            double? number = Finite(value);
            // Upstream AmdGpu initializes this exact channel to -1 before its
            // first successful frame-metrics sample. A negative FPS is not data.
            // This rule is deliberately narrow: battery power/current and other
            // Factor channels may legitimately be signed and remain unchanged.
            if (hardwareType == "GpuAmd" && type == "Factor" && rawName == "Fullscreen FPS" && number < 0)
                return null;
            return number;
        }

        private static string SafeLabel(string label)
        {
            if (String.IsNullOrEmpty(label)) return "Unnamed";
            StringBuilder clean = new StringBuilder(128);
            for (int i = 0; i < label.Length && clean.Length < 128; i++)
            {
                UnicodeCategory category = CharUnicodeInfo.GetUnicodeCategory(label, i);
                int length = Char.IsHighSurrogate(label[i]) && i + 1 < label.Length && Char.IsLowSurrogate(label[i + 1]) ? 2 : 1;
                if (!IsUnicodeOther(category) && clean.Length + length <= 128) clean.Append(label, i, length);
                i += length - 1;
            }
            string result = clean.ToString().Trim();
            return result.Length == 0 ? "Unnamed" : result;
        }

        private static bool ValidId(string id)
        {
            if (String.IsNullOrEmpty(id) || id.Length > 512) return false;
            for (int i = 0; i < id.Length; i++)
            {
                if (IsUnicodeOther(CharUnicodeInfo.GetUnicodeCategory(id, i))) return false;
                if (Char.IsHighSurrogate(id[i]) && i + 1 < id.Length && Char.IsLowSurrogate(id[i + 1])) i++;
            }
            return true;
        }

        private static bool IsUnicodeOther(UnicodeCategory category)
        {
            return category == UnicodeCategory.Control || category == UnicodeCategory.Format ||
                category == UnicodeCategory.Surrogate || category == UnicodeCategory.PrivateUse ||
                category == UnicodeCategory.OtherNotAssigned;
        }

        private static string SerializeBounded(Snapshot snapshot)
        {
            // Full identifiers are kept. Drop trailing rows if UTF-8 would exceed
            // the transport cap, rather than writing a truncated JSON document.
            JavaScriptSerializer serializer = new JavaScriptSerializer();
            serializer.MaxJsonLength = 16 * MaxLineBytes;
            serializer.RecursionLimit = 32;
            while (true)
            {
                string line = serializer.Serialize(snapshot);
                if (Utf8.GetByteCount(line) + 1 <= MaxLineBytes) return line;
                if (snapshot.sensors.Count > 0)
                {
                    int remove = Math.Max(1, snapshot.sensors.Count / 8);
                    snapshot.sensors.RemoveRange(snapshot.sensors.Count - remove, remove);
                    snapshot.truncated += remove;
                }
                else if (snapshot.hardware.Count > 0)
                {
                    snapshot.hardware.RemoveAt(snapshot.hardware.Count - 1);
                    snapshot.truncated++;
                }
                else throw new InvalidOperationException("Empty snapshot exceeds transport limit.");
            }
        }

        private static int SelfTest()
        {
            try
            {
                string unit;
                if (!TryUnit("Energy", out unit) || unit != "mWh") throw new Exception("Energy unit");
                if (!TryUnit("Throughput", out unit) || unit != "B/s") throw new Exception("Throughput unit");
                if (TryUnit("Control", out unit) || TryUnit("Noise", out unit) || TryUnit("Unknown", out unit))
                    throw new Exception("Unsupported type");
                if (Finite(float.NaN) != null || Finite(float.PositiveInfinity) != null || Finite(null) != null || Finite(0f) != 0d)
                    throw new Exception("Finite values");
                if (SensorValue("GpuAmd", "Factor", "Fullscreen FPS", -1f) != null ||
                    SensorValue("GpuAmd", "Factor", "Fullscreen FPS", 0f) != 0d ||
                    SensorValue("GpuAmd", "Factor", "Fullscreen FPS", 60f) != 60d ||
                    SensorValue("GpuAmd", "Factor", "Other factor", -1f) != -1d ||
                    SensorValue("GpuNvidia", "Factor", "Fullscreen FPS", -1f) != -1d ||
                    SensorValue("Battery", "Power", "Charge/Discharge Rate", -15f) != -15d ||
                    SensorValue("Battery", "Current", "Charge/Discharge Current", -1.5f) != -1.5d)
                    throw new Exception("Signed sensor semantics");
                if (SafeLabel("CPU\r\n\u200b\uE000") != "CPU" || SafeLabel(new string('中', 129)).Length != 128 ||
                    ValidId(new string('x', 513)) || ValidId("/test/\n") || !ValidId("/test/battery/energy/0"))
                    throw new Exception("Metadata bounds");
                Options parsed = ParseOptions(new string[] { "--interval", "0.5", "--duration", "15", "--once" });
                if (parsed.Interval != 0.5 || parsed.Duration != 15 || !parsed.Once) throw new Exception("Arguments");
                foreach (string invalid in new string[] { "0.01", "5.01", "NaN", "Infinity", "-1" })
                {
                    bool rejected = false;
                    try { ParseOptions(new string[] { "--interval", invalid }); }
                    catch (ArgumentException) { rejected = true; }
                    if (!rejected) throw new Exception("Interval bounds");
                }
                Snapshot fixture = new Snapshot();
                fixture.timestamp = (DateTime.UtcNow - Epoch).TotalSeconds;
                fixture.hardware.Add(new HardwareRow { id = "/test/battery", name = "Synthetic battery", type = "Battery", parent_id = null });
                fixture.sensors.Add(new SensorRow { id = "/test/battery/energy/0", name = "Synthetic capacity", hardware_id = "/test/battery", hardware_name = "Synthetic battery", hardware_type = "Battery", type = "Energy", unit = "mWh", value = 12345d, min = 12000d, max = 13000d });
                fixture.sensors.Add(new SensorRow { id = "/test/battery/power/0", name = "Synthetic idle", hardware_id = "/test/battery", hardware_name = "Synthetic battery", hardware_type = "Battery", type = "Power", unit = "W", value = 0d, min = 0d, max = 15d });
                string line = SerializeBounded(fixture);
                if (line.IndexOf("\n", StringComparison.Ordinal) >= 0 || line.IndexOf("\"unit\":\"mWh\"", StringComparison.Ordinal) < 0)
                    throw new Exception("NDJSON");
                // Deliberately bypass SafeLabel only in this synthetic stress case
                // to prove the transport cap independently of normal 128-char labels.
                Snapshot large = new Snapshot();
                for (int i = 0; i < MaxSensors; i++)
                    large.sensors.Add(new SensorRow { id = "/test/" + i, name = new string('中', 512), hardware_id = "/test", hardware_name = new string('界', 512), hardware_type = "Storage", type = "Power", unit = "W", value = 0d });
                string bounded = SerializeBounded(large);
                if (Utf8.GetByteCount(bounded) + 1 > MaxLineBytes || large.truncated <= 0) throw new Exception("Line cap");
                Console.Out.WriteLine(line);
                Console.Out.Flush();
                Console.Error.WriteLine("collector synthetic self-test passed; hardware was not opened");
                return 0;
            }
            catch (Exception error)
            {
                Console.Error.WriteLine("collector self-test failed: " + error.GetType().Name + " " + error.Message);
                return 1;
            }
        }
    }
}
