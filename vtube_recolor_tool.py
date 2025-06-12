import json
import asyncio
import websockets
from PyQt5 import QtWidgets, QtGui
import sys
import os

GROUPS_FILE = "artmesh_groups.json"

class VTubeStudioClient:
    def __init__(self):
        self.uri = "ws://localhost:8001"
        self.ws = None
        self.artmeshes = []

    async def connect(self):
        self.ws = await websockets.connect(self.uri)

    async def get_artmeshes(self):
        await self.ws.send(json.dumps({
            "apiName": "VTubeStudioPublicAPI",
            "messageType": "ArtMeshListRequest",
            "data": {}
        }))
        response = await self.ws.recv()
        data = json.loads(response)
        self.artmeshes = data["data"]["artMeshes"]
        return self.artmeshes

    async def tint_artmesh(self, name_exact, r, g, b, a):
        await self.ws.send(json.dumps({
            "apiName": "VTubeStudioPublicAPI",
            "messageType": "ColorTintRequest",
            "data": {
                "colorTint": {
                    "colorR": r,
                    "colorG": g,
                    "colorB": b,
                    "colorA": a
                },
                "artMeshMatcher": {
                    "nameExact": name_exact
                }
            }
        }))


class MainWindow(QtWidgets.QWidget):
    def __init__(self, client):
        super().__init__()
        self.client = client
        self.setWindowTitle("VTS Artmesh Color Tool with Groups")
        self.setGeometry(100, 100, 700, 500)

        self.groups = {}
        self.selected_color = QtGui.QColor(255, 255, 255)

        self.init_ui()

    def init_ui(self):
        self.layout = QtWidgets.QVBoxLayout()

        self.list_widget = QtWidgets.QListWidget()
        self.list_widget.setSelectionMode(QtWidgets.QAbstractItemView.MultiSelection)
        self.layout.addWidget(self.list_widget)

        group_bar = QtWidgets.QHBoxLayout()
        self.group_input = QtWidgets.QLineEdit()
        self.group_input.setPlaceholderText("Group name...")
        self.group_add_btn = QtWidgets.QPushButton("Add to Group")
        self.group_add_btn.clicked.connect(self.add_to_group)
        group_bar.addWidget(self.group_input)
        group_bar.addWidget(self.group_add_btn)
        self.layout.addLayout(group_bar)

        color_bar = QtWidgets.QHBoxLayout()
        self.color_picker = QtWidgets.QPushButton("Pick Color")
        self.color_picker.clicked.connect(self.pick_color)
        self.color_apply_btn = QtWidgets.QPushButton("Apply Color to Group")
        self.color_apply_btn.clicked.connect(self.apply_color_to_group)
        color_bar.addWidget(self.color_picker)
        color_bar.addWidget(self.color_apply_btn)
        self.layout.addLayout(color_bar)

        file_bar = QtWidgets.QHBoxLayout()
        self.save_btn = QtWidgets.QPushButton("Save Groups")
        self.save_btn.clicked.connect(self.save_groups)
        self.load_btn = QtWidgets.QPushButton("Load Groups")
        self.load_btn.clicked.connect(self.load_groups)
        file_bar.addWidget(self.save_btn)
        file_bar.addWidget(self.load_btn)
        self.layout.addLayout(file_bar)

        self.setLayout(self.layout)

    def load_artmeshes(self, artmeshes):
        self.list_widget.clear()
        for mesh in artmeshes:
            self.list_widget.addItem(mesh["name"])

    def pick_color(self):
        color = QtWidgets.QColorDialog.getColor()
        if color.isValid():
            self.selected_color = color

    def add_to_group(self):
        group_name = self.group_input.text().strip()
        if not group_name:
            return

        selected_items = self.list_widget.selectedItems()
        if not selected_items:
            return

        self.groups.setdefault(group_name, [])
        for item in selected_items:
            name = item.text()
            if name not in self.groups[group_name]:
                self.groups[group_name].append(name)

        QtWidgets.QMessageBox.information(self, "Group Updated", f"Added to group '{group_name}'.")

    def apply_color_to_group(self):
        group_name = self.group_input.text().strip()
        if not group_name or group_name not in self.groups:
            QtWidgets.QMessageBox.warning(self, "Missing Group", "Group not found.")
            return

        r, g, b, a = self.selected_color.redF(), self.selected_color.greenF(), self.selected_color.blueF(), 1.0
        for name in self.groups[group_name]:
            asyncio.create_task(self.client.tint_artmesh(name, r, g, b, a))

    def save_groups(self):
        with open(GROUPS_FILE, "w") as f:
            json.dump(self.groups, f, indent=4)
        QtWidgets.QMessageBox.information(self, "Saved", f"Groups saved to {GROUPS_FILE}.")

    def load_groups(self):
        if os.path.exists(GROUPS_FILE):
            with open(GROUPS_FILE, "r") as f:
                self.groups = json.load(f)
            QtWidgets.QMessageBox.information(self, "Loaded", f"Groups loaded from {GROUPS_FILE}.")

async def main():
    app = QtWidgets.QApplication(sys.argv)
    client = VTubeStudioClient()
    await client.connect()
    meshes = await client.get_artmeshes()

    window = MainWindow(client)
    window.load_artmeshes(meshes)
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    asyncio.run(main())