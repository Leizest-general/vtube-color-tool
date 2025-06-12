# VTubeStudio Recolor Tool with Grouping

A safe and standalone desktop tool that allows VTubeStudio users to:
- View all available ArtMesh layers
- Organize layers into custom-named color groups
- Recolor entire groups with a single color pick
- Save and load groups to reuse across sessions

## 🔒 Safety and Anonymity
This app is designed with streamer safety in mind:
- **No Internet access**: It communicates only locally with VTubeStudio via its official WebSocket API.
- **No telemetry, logging, or account links**.
- **No external dependencies or installation** required for end-users (provided as a single `.exe`).

---

## 📦 Features
- List and filter ArtMeshes from the currently loaded model
- Create named groups (e.g., `hair`, `eyes`, `accessories`)
- Recolor an entire group at once with a color picker
- Save/load groups using `artmesh_groups.json`

---

## 🧰 How to Use

### 1. Start VTubeStudio and enable API access:
- Settings → Start API → Enable WebSocket (default port: `8001`)

### 2. Run the app:
- If using source: `python vtube_recolor_tool.py`
- If using the `.exe`, just double-click

### 3. Select ArtMeshes and create groups
- Use the UI to pick layers
- Assign them to a group (e.g., `hair`)
- Pick a color and apply it

---

## 🚀 Build Instructions (For Developers)

You can compile the app into a safe standalone `.exe` using:

```bash
pip install pyinstaller
pyinstaller --noconfirm --onefile --windowed vtube_recolor_tool.py
```
Your binary will be in the dist/ folder.

## ✅ Dependencies
websockets

PyQt5

Install with:

bash
Copy
Edit
pip install websockets PyQt5
## 📂 Files
vtube_recolor_tool.py: main source code

artmesh_groups.json: auto-saved when saving groups

dist/vtube_recolor_tool.exe: optional binary for distribution

## 📄 License
MIT License. You may freely use, modify, and distribute.

## 💬 Contact
If you're a streamer and have safety questions, feel free to open an Issue or reach out anonymously.

---

Would you like me to:
- Create the GitHub repo structure for you (e.g., README.md + .gitignore)?
- Or help package this as a `.zip` for easy distribution?

Let me know!
