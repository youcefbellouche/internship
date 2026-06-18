# Change 01: Layer-by-Layer Protocol Logging

**Date:** 2026-06-19  
**Author:** AI Pair Programmer  
**Status:** Implemented & Verified  

---

## 🎯 Goal
By default, both the 5G Standalone Cell Tower simulator (`oCUDU` gNB) and the UE simulator (`srsue`) write all log outputs into single consolidated log files (typically `/tmp/gnb.log` and `/tmp/ue1.log` respectively). This change separates the logs of the core radio protocol layers on both sides into their own individual files under the `docs/` folder:

### gNB (Cell Tower) logs
- **PDCP Layer**: written to `docs/pdcp.log` (with symlink `docs/pcds.log` -> `pdcp.log`)
- **RLC Layer**: written to `docs/rlc.log`
- **MAC Layer**: written to `docs/mac.log`
- **PHY Layer**: written to `docs/phy.log`

### UE (User Equipment) logs
- **PDCP Layer**: written to `docs/ue_pdcp.log` (with symlink `docs/ue_pcds.log` -> `ue_pdcp.log`)
- **RLC Layer**: written to `docs/ue_rlc.log`
- **MAC Layer**: written to `docs/ue_mac.log`
- **PHY Layer**: written to `docs/ue_phy.log`

---

## 🛠️ Implementation Details

### gNB Side Implementation (C++17)

#### 1. New Includes Added to `gnb.cpp`
To perform filesystem lookups and manipulate file directories, `<filesystem>` was added to the top of `/root/internship-repo/project/ocudu/apps/gnb/gnb.cpp`. `<algorithm>` was used to convert layer names to lowercase string formats.

#### 2. Path Detection
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

#### 3. File Sink Allocation & Logger Interception
For each layer (`PDCP`, `RLC`, `MAC`, `PHY`), a new file sink is created using the default contextual text log formatter, and then registered into `ocudulog`:
```cpp
auto& file_sink = ocudulog::fetch_file_sink(
    log_path, 0, true, false, ocudulog::create_contextual_text_formatter());

bool print_context = (layer == "MAC" || layer == "PHY");
ocudulog::fetch_basic_logger(layer, file_sink, print_context);
```

#### 4. Naming Compatibility
To satisfy the requirement to see `pcds.log`, a symlink is dynamically created pointing to `pdcp.log` when the application initializes:
```cpp
std::filesystem::create_symlink("pdcp.log", pcds_path);
```

---

### UE Side Implementation (C++14)

#### 1. C++14 Standard & POSIX APIs
Because the `srsRAN_4G` project uses `-std=c++14` rather than C++17, standard POSIX functions (`stat`, `unlink`, `symlink`) from `<sys/stat.h>` and `<unistd.h>` are used instead of `std::filesystem` to prevent compilation errors.

#### 2. Path Detection & Map Registration in `srsue/src/main.cc`
Immediately after `srslog::init()`, the UE searches for the workspace's `docs` directory and maps the relevant `srslog` basic logger IDs to custom files:
```cpp
  if (!ue_docs_dir.empty()) {
    struct ue_logger_map_t {
      std::vector<std::string> ids;
      std::string filename;
    };
    std::vector<ue_logger_map_t> log_maps = {
      {{"PDCP", "PDCP-NR"}, "pdcp.log"},
      {{"RLC", "RLC-NR"}, "rlc.log"},
      {{"MAC", "MAC-NR"}, "mac.log"},
      {{"PHY", "PHY-SA", "PHY_LIB", "PHY0", "PHY1", "PHY2", "PHY3", "PHY4", "PHY5", "PHY6", "PHY7"}, "phy.log"}
    };

    for (const auto& mapping : log_maps) {
      std::string log_path = ue_docs_dir + "/ue_" + mapping.filename;
      auto& file_sink = srslog::fetch_file_sink(log_path);
      for (const auto& id : mapping.ids) {
        srslog::fetch_basic_logger(id, file_sink, false);
      }
    }
    
    // Create symlink for ue_pcds.log
    std::string pcds_path = ue_docs_dir + "/ue_pcds.log";
    if (unlink(pcds_path.c_str()) == 0) {}
    if (symlink("ue_pdcp.log", pcds_path.c_str()) == 0) {}
  }
```

This ensures that the UE maps both standard LTE logger IDs (like `PHY`, `MAC`, `RLC`, `PDCP`) and 5G NR logger IDs (like `PHY-SA`, `MAC-NR`, `RLC-NR`, `PDCP-NR`) to their respective files in `docs/` prefixed with `ue_`.

---

## 🚀 Rebuilding & Running

### Rebuild and Run the Tower (gNB)
1. **Compile**:
   ```bash
   cd project/ocudu/build
   make -j$(nproc)
   ```
2. **Run**:
   ```bash
   sudo ./apps/gnb/gnb -c ../../gnb.zmq.yaml
   ```

### Rebuild and Run the UE
1. **Compile & Install**:
   ```bash
   cd project/srsRAN_4G/build
   make srsue -j$(nproc)
   sudo make install && sudo ldconfig
   ```
2. **Run**:
   ```bash
   sudo srsue ../../ue_zmq.conf
   ```

Once traffic starts flowing, separate logs for both the cell tower and user equipment will populate dynamically in the `docs/` directory.
