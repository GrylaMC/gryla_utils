# Gryla McJar.py

A general-purpose utility for downloading and deobfuscating Minecraft JAR files. This tool handles fetching vanilla binaries, resolving mappings (Yarn, Mojang, Spigot, RetroMCP), and remapping JARs to named namespaces.

## Features

- **Vanilla Downloads:** Fetch client or server JARs from Mojang's Piston meta or OmniArchive.
- **Mapping Support:**
  - **Yarn:** Automatic lookup for Fabric's Yarn mappings (Modern and Legacy).
  - **Mojang:** Official Mojang obfuscation maps.
  - **Spigot:** BuildData-based remapping for server JARs.
  - **RetroMCP:** Support for historical versions via MCPHackers.
- **Smart Caching:** Avoids redundant downloads and remapping operations by storing artifacts in `~/.cache/gryla` (or OS equivalent).

## Prerequisites

- **Python 3.8+**
- **Java JRE/JDK:** Required for the remapping tools (Tiny Remapper, SpecialSource-2, etc.).
- **Git:** Required for cloning Spigot BuildData.

## Usage

### 1. Download a Vanilla JAR
Download a specific version without remapping. Use `@omni@` prefix for OmniArchive versions.

```bash
mcjar get 1.20.1 client -o minecraft_1.20.1.jar
mcjar get @omni@b1.7.3 server
```

### 2. Remap a JAR
Download and remap a JAR to named mappings using a specified mapping provider.

**Using Yarn (Default):**
```bash
mcjar remap 1.20.1 client -m yarn
```

**Using Mojang Mappings:**
```bash
mcjar remap 1.19.2 server -m mojang -o server-mapped.jar
```

**Using Spigot Mappings:**
```bash
mcjar remap 1.12.2 server -m spigot
```

**Using RetroMCP (for older versions):**
```bash
mcjar remap b1.7.3 client -m retromcp
```

### 3. Cache Management
Clear the local cache directory to free up space or force fresh downloads.

```bash
mcjar clear_cache
```

## Configuration

The storage directory can be overridden by setting the `GRYLA_HOME` environment variable. By default, it uses:
- **Linux:** `$XDG_CACHE_HOME/gryla` or `~/.cache/gryla`
- **macOS:** `~/Library/Caches/gryla`
- **Windows:** `%LOCALAPPDATA%\gryla\Cache`

## License
AGPL-V3
