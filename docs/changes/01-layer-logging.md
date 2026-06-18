# Change 01: Layer-by-Layer Protocol Logging

**Date:** 2026-06-19  
**Author:** AI Pair Programmer  
**Status:** Implemented & Verified  

---

## 🎯 Goal
By default, the 5G Standalone Cell Tower simulator (`oCUDU` gNB) writes all log outputs into a single consolidated log file (typically `/tmp/gnb.log` or `stdout`). This change separates the logs of the core radio protocol layers into their own files under the `docs/` folder:
- **PDCP Layer**: written to `docs/pdcp.log` and symlinked to `docs/pcds.log`
- **RLC Layer**: written to `docs/rlc.log`
- **MAC Layer**: written to `docs/mac.log`
- **PHY Layer**: written to `docs/phy.log`

---

## 🛠️ Implementation Details

### 1. New Includes Added to `gnb.cpp`
To perform filesystem lookups and manipulate file directories, `<filesystem>` was added to the top of `/root/internship-repo/project/ocudu/apps/gnb/gnb.cpp`. `<algorithm>` was used to convert layer names to lowercase string formats.

### 2. Path Detection
Within the `register_app_logs` initialization function, the binary dynamically searches for the main workspace `docs/` folder using relative and absolute paths to ensure compatibility regardless of where the binary is launched:
```cpp
std::string docs_dir = "";
for (const char* path : {"/root/internship-repo/docs", "../../../docs", "docs", "../docs", "../../docs"}) {
  if (std::filesystem::exists(path) && std::filesystem::is_directory(path)) {
    docs_dir = path;
    break;
  }
}
```

### 3. File Sink Allocation & Logger Interception
For each layer (`PDCP`, `RLC`, `MAC`, `PHY`), a new file sink is created using the default contextual text log formatter, and then registered into `ocudulog`:
```cpp
auto& file_sink = ocudulog::fetch_file_sink(
    log_path, 0, true, false, ocudulog::create_contextual_text_formatter());

bool print_context = (layer == "MAC" || layer == "PHY");
ocudulog::fetch_basic_logger(layer, file_sink, print_context);
```
Since this initialization runs at the start of logging setup, subsequent lookups of these layers throughout the stack retrieve the custom-sink logger instead of the default global-sink one.

### 4. Naming Compatibility
To satisfy the requirement to see `pcds.log`, a symlink is dynamically created pointing to `pdcp.log` when the application initializes:
```cpp
std::filesystem::create_symlink("pdcp.log", pcds_path);
```

---

## 🚀 Rebuilding & Running

To compile the changes:
```bash
cd project/ocudu/build
make -j$(nproc)
```

To run the tower (gNB):
```bash
sudo ./apps/gnb/gnb -c ../../gnb.zmq.yaml
```
Once traffic starts flowing (e.g. when the UE connects or ping requests are sent), logs are immediately outputted to the `docs/` folder in the root of the repository.
