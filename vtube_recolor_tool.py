import json
import asyncio
import qasync
import websockets
from PyQt5 import QtWidgets, QtGui, QtCore
import sys
import os

GROUPS_FILE = "artmesh_groups.json"

class VTubeStudioClient:
    def __init__(self):
        self.uri = "ws://localhost:8001"
        self.ws = None
        self.artmeshes = []

    async def connect(self):
        try:
            self.ws = await websockets.connect(self.uri)
            return True
        except Exception as e:
            print(f"Connection failed: {e}")
            return False

    async def authenticate(self):
        # Try reading token from file, else request one
        try:
            with open("auth_token.txt", "r") as f:
                token = f.read().strip()
        except FileNotFoundError:
            token = await self.request_auth_token()

        await self.ws.send(json.dumps({
            "apiName": "VTubeStudioPublicAPI",
            "apiVersion": "1.0",
            "messageType": "AuthenticationRequest",
            "data": {
                "pluginName": "Vtube Recolor Tool",
                "pluginDeveloper": "Leizest",
                "authenticationToken": token
            }
        }))
        response = await self.ws.recv()
        data = json.loads(response)

        if not data["data"].get("authenticated", False):
            raise RuntimeError("Authentication failed. Invalid token?")

    async def request_auth_token(self):
        await self.ws.send(json.dumps({
            "apiName": "VTubeStudioPublicAPI",
            "apiVersion": "1.0",
            "messageType": "AuthenticationTokenRequest",
            "data": {
                "pluginName": "Vtube Recolor Tool",
                "pluginDeveloper": "Leizest"
            }
        }))
        response = await self.ws.recv()
        data = json.loads(response)
        token = data["data"]["authenticationToken"]
        with open("auth_token.txt", "w") as f:
            f.write(token)
        return token

    async def get_artmeshes(self):
        await self.ws.send(json.dumps({
            "apiName": "VTubeStudioPublicAPI",
            "apiVersion": "1.0",
            "messageType": "ArtMeshListRequest",
            "data": {}
        }))
        response = await self.ws.recv()
        data = json.loads(response)
        names = data["data"].get("artMeshNames", [])
        self.artmeshes = [{"name": n} for n in names]
        return self.artmeshes

    async def tint_artmesh(self, name_exact, r, g, b, a):
        msg = {
            "apiName": "VTubeStudioPublicAPI",
            "apiVersion": "1.0",
            "messageType": "ColorTintRequest",
            "data": {
                "colorTint": {
                    "colorR": r,
                    "colorG": g,
                    "colorB": b,
                    "colorA": a
                },
                "artMeshMatcher": {
                    "tintAll": False,
                    "nameExact": name_exact
                }
            }
        }
        print(f"Sending tint request for: {name_exact} with color ({r:.3f}, {g:.3f}, {b:.3f}, {a:.3f})")
        await self.ws.send(json.dumps(msg))
        
        try:
            # Wait for response to ensure the command was processed
            response = await self.ws.recv()
            result = json.loads(response)
            print(f"Response for {name_exact}: {result}")
            return result
        except Exception as e:
            print(f"Error receiving response for {name_exact}: {e}")
            return {"data": {"matchedArtMeshes": 0}}
        
    async def tint_artmesh_exact(self, name_exact, r, g, b, a):
        """Tint using exact name matching"""
        msg = {
            "apiName": "VTubeStudioPublicAPI",
            "apiVersion": "1.0",
            "messageType": "ColorTintRequest",
            "data": {
                "colorTint": {
                    "colorR": int(r * 255),
                    "colorG": int(g * 255),
                    "colorB": int(b * 255),
                    "colorA": int(a * 255)
                },
                "artMeshMatcher": {
                    "tintAll": False,
                    "nameExact": [name_exact]
                }
            }
        }
        print(f"Sending exact tint request for: {name_exact}")
        await self.ws.send(json.dumps(msg))
        
        try:
            response = await self.ws.recv()
            result = json.loads(response)
            return result
        except Exception as e:
            print(f"Error receiving response for {name_exact}: {e}")
            return {"data": {"matchedArtMeshes": 0}}

    async def tint_artmesh_contains(self, name_contains, r, g, b, a):
        """Tint using contains matching as fallback"""
        msg = {
            "apiName": "VTubeStudioPublicAPI",
            "apiVersion": "1.0",
            "messageType": "ColorTintRequest",
            "data": {
                "colorTint": {
                    "colorR": int(r * 255),
                    "colorG": int(g * 255),
                    "colorB": int(b * 255),
                    "colorA": int(a * 255)
                },
                "artMeshMatcher": {
                    "tintAll": False,
                    "nameContains": [name_contains]
                }
            }
        }
        print(f"Sending contains tint request for: {name_contains}")
        await self.ws.send(json.dumps(msg))
        
        try:
            response = await self.ws.recv()
            result = json.loads(response)
            return result
        except Exception as e:
            print(f"Error receiving response for {name_contains}: {e}")
            return {"data": {"matchedArtMeshes": 0}}


class ColorPreviewWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.color = QtGui.QColor(255, 255, 255)
        self.setFixedSize(40, 40)
        self.setStyleSheet("border: 2px solid black; border-radius: 5px;")

    def set_color(self, color):
        self.color = color
        self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.fillRect(self.rect(), self.color)


class StatusBar(QtWidgets.QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setText("Ready")
        self.setStyleSheet("QLabel { background-color: #f0f0f0; padding: 5px; border-top: 1px solid #ccc; }")

    def show_message(self, message, timeout=3000):
        self.setText(message)
        if timeout > 0:
            QtCore.QTimer.singleShot(timeout, lambda: self.setText("Ready"))


class MainWindow(QtWidgets.QWidget):
    def __init__(self, client):
        super().__init__()
        self.client = client
        self.setWindowTitle("VTS Artmesh Color Tool with Groups")
        self.setGeometry(100, 100, 900, 600)

        self.groups = {}  # group_name: { "color": [r,g,b], "layers": [names...] }
        self.selected_color = QtGui.QColor(255, 255, 255)
        self.current_artmeshes = []  # Store current artmesh names for validation

        self.init_ui()
        self.load_groups()  # Auto-load groups on startup

    def init_ui(self):
        main_layout = QtWidgets.QVBoxLayout()

        # Add refresh button at the top
        refresh_layout = QtWidgets.QHBoxLayout()
        self.refresh_btn = QtWidgets.QPushButton("🔄 Refresh Artmeshes")
        self.refresh_btn.clicked.connect(self.refresh_artmeshes_clicked)
        self.refresh_btn.setStyleSheet("QPushButton { background-color: #9C27B0; color: white; font-weight: bold; }")
        refresh_layout.addWidget(self.refresh_btn)
        refresh_layout.addStretch()
        main_layout.addLayout(refresh_layout)

        # Create horizontal layout for main content
        content_layout = QtWidgets.QHBoxLayout()

        # Left panel - Layers
        left_panel = QtWidgets.QVBoxLayout()
        left_panel.addWidget(QtWidgets.QLabel("<b>Available Layers</b>"))
        
        # Search box for layers
        self.layer_search = QtWidgets.QLineEdit()
        self.layer_search.setPlaceholderText("Search layers...")
        self.layer_search.textChanged.connect(self.filter_layers)
        left_panel.addWidget(self.layer_search)
        
        self.layer_list = QtWidgets.QListWidget()
        self.layer_list.setSelectionMode(QtWidgets.QAbstractItemView.MultiSelection)
        self.layer_list.setSortingEnabled(True)
        left_panel.addWidget(self.layer_list)
        
        # Layer count label
        self.layer_count_label = QtWidgets.QLabel("Layers: 0")
        self.layer_count_label.setStyleSheet("QLabel { font-size: 10px; color: #666; }")
        left_panel.addWidget(self.layer_count_label)
        
        content_layout.addLayout(left_panel, 1)

        # Middle panel - Assignment buttons
        middle_panel = QtWidgets.QVBoxLayout()
        middle_panel.addStretch()
        
        self.assign_btn = QtWidgets.QPushButton("Add to Group →")
        self.assign_btn.setFixedSize(120, 35)
        self.assign_btn.clicked.connect(self.assign_selected_layers)
        self.assign_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; font-weight: bold; }")
        
        self.remove_btn = QtWidgets.QPushButton("← Remove")
        self.remove_btn.setFixedSize(120, 35)
        self.remove_btn.clicked.connect(self.remove_selected_layers)
        self.remove_btn.setStyleSheet("QPushButton { background-color: #f44336; color: white; font-weight: bold; }")
        
        middle_panel.addWidget(self.assign_btn)
        middle_panel.addWidget(self.remove_btn)
        middle_panel.addStretch()
        
        content_layout.addLayout(middle_panel, 0)

        # Right panel - Groups
        right_panel = QtWidgets.QVBoxLayout()
        right_panel.addWidget(QtWidgets.QLabel("<b>Groups</b>"))
        
        # Group creation controls
        group_create_layout = QtWidgets.QHBoxLayout()
        self.group_input = QtWidgets.QLineEdit()
        self.group_input.setPlaceholderText("New group name")
        self.group_input.returnPressed.connect(self.create_group)
        self.add_group_btn = QtWidgets.QPushButton("Create")
        self.add_group_btn.clicked.connect(self.create_group)
        self.add_group_btn.setStyleSheet("QPushButton { background-color: #2196F3; color: white; }")
        group_create_layout.addWidget(self.group_input)
        group_create_layout.addWidget(self.add_group_btn)
        right_panel.addLayout(group_create_layout)

        self.group_list = QtWidgets.QListWidget()
        self.group_list.itemSelectionChanged.connect(self.update_group_details)
        self.group_list.itemDoubleClicked.connect(self.rename_group)
        right_panel.addWidget(self.group_list)

        # Group details
        group_detail_layout = QtWidgets.QVBoxLayout()
        group_detail_layout.addWidget(QtWidgets.QLabel("<b>Group Contents</b>"))
        self.group_detail = QtWidgets.QListWidget()
        self.group_detail.setSelectionMode(QtWidgets.QAbstractItemView.MultiSelection)
        group_detail_layout.addWidget(self.group_detail)
        right_panel.addLayout(group_detail_layout)

        # Color controls
        color_layout = QtWidgets.QHBoxLayout()
        self.color_preview = ColorPreviewWidget()
        self.color_picker = QtWidgets.QPushButton("Pick Color")
        self.color_picker.clicked.connect(self.pick_color)
        self.apply_color_btn = QtWidgets.QPushButton("Apply Color")
        self.apply_color_btn.clicked.connect(self.apply_color_clicked)
        self.apply_color_btn.setStyleSheet("QPushButton { background-color: #FF9800; color: white; font-weight: bold; }")
        
        color_layout.addWidget(QtWidgets.QLabel("Color:"))
        color_layout.addWidget(self.color_preview)
        color_layout.addWidget(self.color_picker)
        color_layout.addWidget(self.apply_color_btn)
        right_panel.addLayout(color_layout)

        # Group management buttons
        group_mgmt_layout = QtWidgets.QHBoxLayout()
        self.delete_group_btn = QtWidgets.QPushButton("Delete Group")
        self.delete_group_btn.clicked.connect(self.delete_group)
        self.delete_group_btn.setStyleSheet("QPushButton { background-color: #f44336; color: white; }")
        
        self.clear_group_btn = QtWidgets.QPushButton("Clear Group")
        self.clear_group_btn.clicked.connect(self.clear_group)
        
        self.validate_btn = QtWidgets.QPushButton("Validate Names")
        self.validate_btn.clicked.connect(self.validate_group_names)
        self.validate_btn.setStyleSheet("QPushButton { background-color: #FF5722; color: white; }")
        
        group_mgmt_layout.addWidget(self.delete_group_btn)
        group_mgmt_layout.addWidget(self.clear_group_btn)
        group_mgmt_layout.addWidget(self.validate_btn)
        right_panel.addLayout(group_mgmt_layout)

        # File controls
        file_layout = QtWidgets.QHBoxLayout()
        self.save_btn = QtWidgets.QPushButton("Save Groups")
        self.load_btn = QtWidgets.QPushButton("Load Groups")
        self.save_btn.clicked.connect(self.save_groups)
        self.load_btn.clicked.connect(self.load_groups)
        file_layout.addWidget(self.save_btn)
        file_layout.addWidget(self.load_btn)
        right_panel.addLayout(file_layout)

        content_layout.addLayout(right_panel, 2)
        main_layout.addLayout(content_layout)

        # Status bar
        self.status_bar = StatusBar()
        main_layout.addWidget(self.status_bar)

        self.setLayout(main_layout)

    def filter_layers(self, text):
        for i in range(self.layer_list.count()):
            item = self.layer_list.item(i)
            item.setHidden(text.lower() not in item.text().lower())

    def load_artmeshes(self, artmeshes):
        self.layer_list.clear()
        self.current_artmeshes = []
        for mesh in artmeshes:
            self.layer_list.addItem(mesh["name"])
            self.current_artmeshes.append(mesh["name"])
        self.layer_count_label.setText(f"Layers: {len(artmeshes)}")
        self.status_bar.show_message(f"Loaded {len(artmeshes)} artmeshes")

    def refresh_artmeshes_clicked(self):
        """Wrapper to call async refresh from button click"""
        loop = asyncio.get_event_loop()
        # Use ensure_future to properly schedule the coroutine
        asyncio.ensure_future(self.refresh_artmeshes())

    async def refresh_artmeshes(self):
        """Refresh the artmesh list from VTube Studio"""
        try:
            self.status_bar.show_message("Refreshing artmeshes...")
            meshes = await self.client.get_artmeshes()
            self.load_artmeshes(meshes)
            self.status_bar.show_message("Artmeshes refreshed successfully")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Refresh Error", f"Failed to refresh artmeshes: {str(e)}")
            self.status_bar.show_message("Refresh failed")

    def validate_group_names(self):
        """Check which artmesh names in groups are valid"""
        group_item = self.group_list.currentItem()
        if not group_item:
            QtWidgets.QMessageBox.warning(self, "No Group Selected", "Please select a group first.")
            return
        
        group_name = group_item.text()
        layers = self.groups[group_name]["layers"]
        
        if not layers:
            QtWidgets.QMessageBox.information(self, "Empty Group", "The selected group has no layers.")
            return
        
        valid_names = []
        invalid_names = []
        case_mismatch_names = []
        
        # Create lowercase lookup for case-insensitive matching
        artmesh_lookup = {name.lower(): name for name in self.current_artmeshes}
        
        for layer in layers:
            layer_lower = layer.lower()
            if layer in self.current_artmeshes:
                # Exact match
                valid_names.append(layer)
            elif layer_lower in artmesh_lookup:
                # Case mismatch - store both the stored name and actual name
                actual_name = artmesh_lookup[layer_lower]
                case_mismatch_names.append((layer, actual_name))
            else:
                # No match at all
                invalid_names.append(layer)
        
        # Show results
        message = f"Group: {group_name}\n\n"
        message += f"Exact matches ({len(valid_names)}):\n"
        for name in valid_names[:10]:
            message += f"  ✓ {name}\n"
        if len(valid_names) > 10:
            message += f"  ... and {len(valid_names) - 10} more\n"
        
        if case_mismatch_names:
            message += f"\nCase mismatches ({len(case_mismatch_names)}):\n"
            for stored_name, actual_name in case_mismatch_names[:10]:
                message += f"  ⚠ '{stored_name}' → '{actual_name}'\n"
            if len(case_mismatch_names) > 10:
                message += f"  ... and {len(case_mismatch_names) - 10} more\n"
        
        message += f"\nNo matches ({len(invalid_names)}):\n"
        for name in invalid_names[:10]:
            message += f"  ✗ {name}\n"
        if len(invalid_names) > 10:
            message += f"  ... and {len(invalid_names) - 10} more\n"
        
        # Suggest fixing case mismatches
        if case_mismatch_names:
            reply = QtWidgets.QMessageBox.question(
                self, "Fix Case Mismatches?",
                message + f"\n\nWould you like to automatically fix the {len(case_mismatch_names)} case mismatches?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
            )
            
            if reply == QtWidgets.QMessageBox.Yes:
                # Fix case mismatches
                for stored_name, actual_name in case_mismatch_names:
                    idx = self.groups[group_name]["layers"].index(stored_name)
                    self.groups[group_name]["layers"][idx] = actual_name
                
                self.update_group_details()
                self.status_bar.show_message(f"Fixed {len(case_mismatch_names)} case mismatches")
                return
        
        # Show suggestions for completely invalid names
        if invalid_names:
            message += f"\nSuggestions for invalid names:\n"
            for invalid_name in invalid_names[:5]:
                suggestions = self.find_similar_names(invalid_name)
                if suggestions:
                    message += f"  '{invalid_name}' → maybe: {', '.join(suggestions[:3])}\n"
        
        QtWidgets.QMessageBox.information(self, "Name Validation Results", message)

    def find_similar_names(self, target_name, max_suggestions=3):
        """Find similar artmesh names using simple string matching"""
        target_lower = target_name.lower()
        suggestions = []
        
        # Look for names containing parts of the target
        for name in self.current_artmeshes:
            name_lower = name.lower()
            # Check for partial matches
            if any(part in name_lower for part in target_lower.split('_') if len(part) > 2):
                suggestions.append(name)
            elif target_lower in name_lower or name_lower in target_lower:
                suggestions.append(name)
        
        return suggestions[:max_suggestions]

    def create_group(self):
        name = self.group_input.text().strip()
        if not name:
            QtWidgets.QMessageBox.warning(self, "Invalid Input", "Group name cannot be empty.")
            return
        if name in self.groups:
            QtWidgets.QMessageBox.warning(self, "Duplicate Name", "Group name already exists.")
            return
        self.groups[name] = {"color": [255, 255, 255], "layers": []}
        self.group_list.addItem(name)
        self.group_input.clear()
        self.status_bar.show_message(f"Created group: {name}")

    def delete_group(self):
        group_item = self.group_list.currentItem()
        if not group_item:
            QtWidgets.QMessageBox.warning(self, "No Selection", "Please select a group to delete.")
            return
        
        group_name = group_item.text()
        reply = QtWidgets.QMessageBox.question(
            self, "Confirm Delete", 
            f"Are you sure you want to delete group '{group_name}'?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        
        if reply == QtWidgets.QMessageBox.Yes:
            del self.groups[group_name]
            self.group_list.takeItem(self.group_list.row(group_item))
            self.group_detail.clear()
            self.status_bar.show_message(f"Deleted group: {group_name}")

    def clear_group(self):
        group_item = self.group_list.currentItem()
        if not group_item:
            QtWidgets.QMessageBox.warning(self, "No Selection", "Please select a group to clear.")
            return
        
        group_name = group_item.text()
        self.groups[group_name]["layers"] = []
        self.update_group_details()
        self.status_bar.show_message(f"Cleared group: {group_name}")

    def rename_group(self, item):
        old_name = item.text()
        new_name, ok = QtWidgets.QInputDialog.getText(
            self, "Rename Group", "Enter new group name:", text=old_name
        )
        
        if ok and new_name.strip() and new_name != old_name:
            new_name = new_name.strip()
            if new_name in self.groups:
                QtWidgets.QMessageBox.warning(self, "Duplicate Name", "Group name already exists.")
                return
            
            self.groups[new_name] = self.groups.pop(old_name)
            item.setText(new_name)
            self.status_bar.show_message(f"Renamed group: {old_name} → {new_name}")

    def update_group_details(self):
        self.group_detail.clear()
        group_item = self.group_list.currentItem()
        if not group_item:
            return
        
        group_name = group_item.text()
        layers = self.groups[group_name]["layers"]
        
        # Add visual indicators for valid/invalid names
        for layer in layers:
            item = QtWidgets.QListWidgetItem()
            if layer in self.current_artmeshes:
                item.setText(f"✓ {layer}")
                item.setForeground(QtGui.QColor(0, 150, 0))  # Green for valid
            else:
                item.setText(f"✗ {layer}")
                item.setForeground(QtGui.QColor(200, 0, 0))  # Red for invalid
            self.group_detail.addItem(item)
        
        # Update color preview
        color_rgb = self.groups[group_name]["color"]
        color = QtGui.QColor(color_rgb[0], color_rgb[1], color_rgb[2])
        self.color_preview.set_color(color)
        self.selected_color = color

    def assign_selected_layers(self):
        group_item = self.group_list.currentItem()
        if not group_item:
            QtWidgets.QMessageBox.warning(self, "No Group Selected", "Please select a group first.")
            return
        
        group_name = group_item.text()
        selected_layers = [item.text() for item in self.layer_list.selectedItems()]
        
        if not selected_layers:
            QtWidgets.QMessageBox.warning(self, "No Layers Selected", "Please select layers to assign.")
            return
        
        added_count = 0
        for layer in selected_layers:
            if layer not in self.groups[group_name]["layers"]:
                self.groups[group_name]["layers"].append(layer)
                added_count += 1
        
        self.update_group_details()
        self.status_bar.show_message(f"Added {added_count} layers to {group_name}")

    def remove_selected_layers(self):
        group_item = self.group_list.currentItem()
        if not group_item:
            QtWidgets.QMessageBox.warning(self, "No Group Selected", "Please select a group first.")
            return
        
        group_name = group_item.text()
        selected_items = self.group_detail.selectedItems()
        
        if not selected_items:
            QtWidgets.QMessageBox.warning(self, "No Layers Selected", "Please select layers to remove.")
            return
        
        # Extract actual layer names (remove the ✓/✗ prefix)
        selected_layers = []
        for item in selected_items:
            text = item.text()
            if text.startswith('✓ ') or text.startswith('✗ '):
                layer_name = text[2:]  # Remove prefix
            else:
                layer_name = text
            selected_layers.append(layer_name)
        
        for layer in selected_layers:
            if layer in self.groups[group_name]["layers"]:
                self.groups[group_name]["layers"].remove(layer)
        
        self.update_group_details()
        self.status_bar.show_message(f"Removed {len(selected_layers)} layers from {group_name}")

    def pick_color(self):
        color = QtWidgets.QColorDialog.getColor(self.selected_color)
        if color.isValid():
            self.selected_color = color
            self.color_preview.set_color(color)

    def apply_color_clicked(self):
        """Wrapper to call async apply_color from button click"""
        loop = asyncio.get_event_loop()
        # Use ensure_future to properly schedule the coroutine
        asyncio.ensure_future(self.apply_color_to_selected_group())

    async def apply_color_to_selected_group(self):
        group_item = self.group_list.currentItem()
        if not group_item:
            QtWidgets.QMessageBox.warning(self, "No Group Selected", "Please select a group first.")
            return
        
        group_name = group_item.text()
        layers = self.groups[group_name]["layers"]
        
        if not layers:
            QtWidgets.QMessageBox.warning(self, "Empty Group", "The selected group has no layers.")
            return
        
        # Create case-insensitive lookup
        artmesh_lookup = {name.lower(): name for name in self.current_artmeshes}
        
        # Filter and fix case issues
        valid_layers = []
        case_fixed_layers = []
        invalid_layers = []
        
        for layer in layers:
            layer_lower = layer.lower()
            if layer in self.current_artmeshes:
                # Exact match
                valid_layers.append(layer)
            elif layer_lower in artmesh_lookup:
                # Case mismatch - use the correct case
                correct_name = artmesh_lookup[layer_lower]
                valid_layers.append(correct_name)
                case_fixed_layers.append((layer, correct_name))
            else:
                # No match
                invalid_layers.append(layer)
        
        if not valid_layers:
            QtWidgets.QMessageBox.warning(
                self, "No Valid Names", 
                f"None of the {len(layers)} artmesh names in this group are currently valid.\n\n"
                f"Use 'Validate Names' to see suggestions or 'Refresh Artmeshes' to update the list."
            )
            return
        
        # Show case fixes if any
        if case_fixed_layers:
            QtWidgets.QMessageBox.information(
                self, "Case Mismatches Fixed",
                f"Fixed {len(case_fixed_layers)} case mismatches automatically:\n" +
                '\n'.join([f"'{old}' → '{new}'" for old, new in case_fixed_layers[:5]]) +
                (f"\n... and {len(case_fixed_layers) - 5} more" if len(case_fixed_layers) > 5 else "")
            )
        
        if invalid_layers:
            reply = QtWidgets.QMessageBox.question(
                self, "Invalid Names Found",
                f"Group contains {len(invalid_layers)} invalid artmesh names.\n\n"
                f"Continue with {len(valid_layers)} valid names only?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
            )
            if reply != QtWidgets.QMessageBox.Yes:
                return

        color = self.selected_color
        self.groups[group_name]["color"] = [color.red(), color.green(), color.blue()]

        # Convert to float values (0.0 to 1.0)
        r, g, b, a = color.redF(), color.greenF(), color.blueF(), 1.0
        
        print(f"Applying color ({r:.3f}, {g:.3f}, {b:.3f}, {a:.3f}) to group '{group_name}' with {len(valid_layers)} valid layers")
        self.status_bar.show_message(f"Applying colors to {len(valid_layers)} layers...")
        
        try:
            success_count = 0
            failed_layers = []
            
            for name in valid_layers:
                try:
                    # Try nameExact first
                    result = await self.client.tint_artmesh_exact(name, r, g, b, a)
                    
                    # Check the actual matchedArtMeshes count
                    success = False
                    if isinstance(result.get("data"), dict):
                        matched_count = result["data"].get("matchedArtMeshes", 0)
                        success = matched_count > 0
                    
                    if success:
                        success_count += 1
                        print(f"✓ Successfully tinted: {name} (matched {matched_count} meshes)")
                    else:
                        # Try nameContains as fallback
                        print(f"Exact match failed for {name}, trying contains match...")
                        result = await self.client.tint_artmesh_contains(name, r, g, b, a)
                        
                        if isinstance(result.get("data"), dict):
                            matched_count = result["data"].get("matchedArtMeshes", 0)
                            success = matched_count > 0
                        
                        if success:
                            success_count += 1
                            print(f"✓ Successfully tinted (contains): {name} (matched {matched_count} meshes)")
                        else:
                            failed_layers.append(name)
                            print(f"✗ Failed both exact and contains: {name}")
                            
                except Exception as e:
                    failed_layers.append(name)
                    print(f"✗ Exception tinting {name}: {e}")
                
                # Small delay to avoid overwhelming the API
                await asyncio.sleep(0.05)
            
            # Show results
            if success_count > 0:
                self.status_bar.show_message(
                    f"Applied color to {success_count}/{len(valid_layers)} layers"
                )
                if failed_layers:
                    QtWidgets.QMessageBox.information(
                        self, "Partial Success",
                        f"Successfully colored {success_count} layers.\n"
                        f"Failed to color {len(failed_layers)} layers:\n" +
                        '\n'.join(failed_layers[:10]) +
                        (f"\n... and {len(failed_layers) - 10} more" if len(failed_layers) > 10 else "")
                    )
            else:
                self.status_bar.show_message("No artmeshes were colored")
                QtWidgets.QMessageBox.warning(
                    self, "No Success", 
                    f"None of the {len(valid_layers)} layers were successfully colored.\n\n"
                    f"Debug info for troubleshooting:\n" +
                    f"First few layer names: {', '.join(valid_layers[:3])}\n\n"
                    f"Try refreshing the artmesh list or check if the correct model is loaded."
                )
                
        except Exception as e:
            error_msg = f"Failed to apply colors: {str(e)}"
            QtWidgets.QMessageBox.critical(self, "Error", error_msg)
            self.status_bar.show_message("Color application failed")
            print(f"Exception in apply_color_to_selected_group: {e}")

    def save_groups(self):
        try:
            with open(GROUPS_FILE, "w") as f:
                json.dump(self.groups, f, indent=4)
            self.status_bar.show_message("Groups saved successfully")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Save Error", f"Failed to save groups: {str(e)}")

    def load_groups(self):
        if not os.path.exists(GROUPS_FILE):
            return  # Silent fail on startup
        
        try:
            with open(GROUPS_FILE, "r") as f:
                self.groups = json.load(f)
            self.group_list.clear()
            for name in self.groups.keys():
                self.group_list.addItem(name)
            self.group_detail.clear()
            self.status_bar.show_message("Groups loaded successfully")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Load Error", f"Failed to load groups: {str(e)}")


class AppInitializer(QtCore.QObject):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.client = None
        self.window = None

    async def initialize(self):
        self.client = VTubeStudioClient()
        
        # Show a simple connection dialog
        progress = QtWidgets.QProgressDialog("Connecting to VTube Studio...", "Cancel", 0, 0)
        progress.setWindowModality(QtCore.Qt.WindowModal)
        progress.show()
        self.app.processEvents()
        
        try:
            connected = await self.client.connect()
            if not connected:
                progress.close()
                QtWidgets.QMessageBox.critical(None, "Connection Error", 
                                             "Failed to connect to VTube Studio. Make sure VTube Studio is running and the API is enabled.")
                self.app.quit()
                return
            
            await self.client.authenticate()
            meshes = await self.client.get_artmeshes()
            
            progress.close()
            
            self.window = MainWindow(self.client)
            self.window.load_artmeshes(meshes)
            self.window.show()
            
        except Exception as e:
            progress.close()
            QtWidgets.QMessageBox.critical(None, "Error", f"Failed to initialize: {str(e)}")
            self.app.quit()

def main():
    app = QtWidgets.QApplication(sys.argv)
    
    # Set up the event loop
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)
    
    # Initialize the application
    initializer = AppInitializer(app)
    
    # Start initialization
    loop.create_task(initializer.initialize())
    
    # Run the event loop
    with loop:
        loop.run_forever()

if __name__ == "__main__":
    main()