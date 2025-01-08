import omni.ext
import omni.ui as ui
import logging
import time
from pxr import UsdGeom, Gf
import threading # type: ignore
import os
import omni.kit.commands
import json
import math


class SphereTransformListenerExtension(omni.ext.IExt):
    def on_startup(self, ext_id):
        logging.warning("SphereTransformListenerExtension: Extension startup.")
        
        self.slider = None
        self._sphere_path = None
        print(self._sphere_path)
        self._stage = omni.usd.get_context().get_stage()
        

        # Store the initial position of the sphere
        self._last_position = None
        self._polling_active = False  # Control flag for the polling thread
        self._poll_thread = None  # Reference to the polling thread
        self._text_file_path = os.path.join(os.path.expanduser("~/Documents"), "sphere_transform_data.json")
        self._flag = False


        # Setup UI
        self._window = ui.Window("Location Listener", width=300, height=300)
        with self._window.frame:
            with ui.VStack():

                def add_sphere():
                    logging.warning("Add avatar button clicked.")
                    logging.warning(self._stage)
                    
                    start_position = Gf.Vec3d(200.0, 200.0, 0.0)
                    
                    # Create the sphere
                    omni.kit.commands.execute('CreatePrimWithDefaultXform',
                                            prim_type='Sphere',
                                            attributes={'radius': 50.0})
                    
                    # Get the path to the created sphere
                    self._sphere_path = "/World/Sphere"
                    sphere_prim = self._stage.GetPrimAtPath(self._sphere_path)
                    
                    if sphere_prim.IsValid():
                        xform = UsdGeom.XformCommonAPI(sphere_prim)

                        # Set translation
                        xform.SetTranslate(start_position) 
                        
            
                    
                    logging.warning("Avatar created at position: %s", start_position)
                    self._start_transform_polling()


                def delete_sphere():
                    logging.warning("Delete avatar button clicked.")
                    if self._stage.GetPrimAtPath(self._sphere_path).IsValid():
                        omni.kit.commands.execute('DeletePrims', paths=[self._sphere_path])
                        logging.warning("Avatar deleted.")
                        self._stop_transform_polling()
                        self._remove_file_if_exists()
                        # Reset the label and display entries
                        if hasattr(self, "_data_display"):
                            self._data_display.text = "Data will display here."
                            self._display_entries = []  # Clear any tracked entries
                    else:
                        logging.warning("Avatar doesn't exist.")
                    

                ui.Button("Add avatar", clicked_fn=add_sphere)
                ui.Button("Delete avatar", clicked_fn=delete_sphere)
                self._slider = ui.IntSlider(min=0,max=10,name="Acuraccy")
                self._data_display = ui.Label("Data will appear here.")
        
        
    def _start_transform_polling(self):
        """Starts the polling thread for tracking sphere transforms."""
        if not self._polling_active:  # Only start if not already active
            self._polling_active = True
            self._poll_thread = threading.Thread(target=self._poll_transform, daemon=True)
            self._poll_thread.start()
            logging.warning("Polling thread started.")

    def _stop_transform_polling(self):
        """Stops the polling thread."""
        self._polling_active = False
        if self._poll_thread:
            self._poll_thread.join()  # Wait for the thread to finish
            self._poll_thread = None
            logging.warning("Polling thread stopped.")

    def _poll_transform(self):
        """Polls the sphere's transform to check for changes."""
        while self._polling_active:
            time.sleep(1)  # Poll every second
            logging.warning("Scanning...")
            logging.warning(f"SLIDER: {self._slider.model.as_int}")
            self._check_sphere_transform()

    def _check_sphere_transform(self):
        """Checks the sphere's current transform and logs it if changed."""
        prim = self._stage.GetPrimAtPath(self._sphere_path)
        if prim and prim.IsValid():
            # Get the current transform of the sphere
            xform = UsdGeom.Xform(prim)
            # Extract the translation part (x, y, z) from the local-to-world matrix
            matrix = xform.ComputeLocalToWorldTransform(0)
            position = matrix.ExtractTranslation()  # Extract position (x, y, z)

            # If the position has changed, log and send the data
            if self._last_position is None or position != self._last_position:
                self._last_position = position
                logging.warning(f"Avatar moved! New position: {position}")
                self._send_data_to_backend(position)
                self._receive_data_from_backend()
                


   

    def _send_data_to_backend(self, position):

        directory = os.path.expanduser("~/Documents")
        json_file_path = os.path.join(directory, "sphere_transform_data.json")
        
        try:
            # Convert Cartesian coordinates to latitude and longitude
            x, y, z = position
            radius = math.sqrt(x**2 + y**2 + z**2)
            latitude = math.degrees(math.asin(z / radius))
            longitude = math.degrees(math.atan2(y, x))

            # Safely fetch the slider value for accuracy
            accuracy = self._slider.model.as_int if self._slider else None
            if accuracy is None:
                logging.warning("Accuracy slider value is not available. Setting to default (0).")
                accuracy = 0

            # Load existing data or initialize with an empty list
            data = []
            if os.path.exists(json_file_path):

                if os.path.getsize(json_file_path) > 0:
                    try:
                        with open(json_file_path, "r") as file:
                            data = json.load(file)
                    except json.JSONDecodeError:
                        logging.warning(f"File {json_file_path} is invalid.")
                else:
                    logging.warning(f"File {json_file_path} is empty. Initializing with an empty list.")

            # Append the new position data
            entry = {
                "action": "created" if not self._flag else "moved",
                "longitude": round(longitude, 6),
                "latitude": round(latitude, 6),
                "accuracy": accuracy
            }
            data.append(entry)
            self._flag = True

            # Write updated data back to the file
            with open(json_file_path, "w") as file:
                json.dump(data, file, indent=4)

            logging.warning(f"Longitude, latitude, and accuracy logged to {json_file_path}: ({longitude}, {latitude}), {accuracy}")
        except PermissionError as e:
            logging.error(f"PermissionError: Unable to write to {json_file_path}. Details: {e}")
        except Exception as e:
            logging.error(f"Unexpected error while writing to {json_file_path}: {e}")


    def _receive_data_from_backend(self):
        """Reads data from the JSON file and updates the UI label."""
        # Construct the file path
        json_file_path = os.path.join(os.path.expanduser("~/Documents"), "sphere_transform_data.json")

        try:
            # Load the JSON file
            if os.path.exists(json_file_path) and os.path.getsize(json_file_path) > 0:
                with open(json_file_path, "r") as file:
                    data = json.load(file)  # Load existing JSON data
                
                # Format and append the data to the label's text
                display_entries = getattr(self, "_display_entries", []) 
                
                for entry in data[-7:]:  # Get the last 7 entries from the JSON file
                    longitude = entry.get('longitude', 'N/A')
                    latitude = entry.get('latitude', 'N/A')
                    accuracy = entry.get('accuracy', 'N/A')
                    action = entry.get('action', 'Unknown')
                    message = f"{action}: Longitude {longitude}, Latitude {latitude}, Accuracy {accuracy}"
                    display_entries.append(message)
                
                # Keep only the last 7 entries
                display_entries = display_entries[-7:]
                self._display_entries = display_entries  # Save back to the attribute

                # Update the label text
                self._data_display.text = "\n".join(display_entries)
            else:
                self._data_display.text = "No data available."
        except Exception as e:
            logging.error(f"Error reading JSON file: {e}")
            self._data_display.text = "Error reading data."


    
    def _remove_file_if_exists(self):
        """Removes the file if it exists."""
        if os.path.exists(self._text_file_path):
            try:
                os.remove(self._text_file_path)
                logging.warning(f"File {self._text_file_path} removed.")
            except PermissionError as e:
                logging.error(f"PermissionError: Unable to delete {self._text_file_path}. Details: {e}")
            except Exception as e:
                logging.error(f"Unexpected error while deleting {self._text_file_path}: {e}")



    def on_shutdown(self):
        logging.warning("SphereTransformListenerExtension: Extension shutdown.")
        self._stop_transform_polling()
