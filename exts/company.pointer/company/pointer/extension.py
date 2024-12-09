import omni.ext
import omni.ui as ui
import logging
import time
from pxr import UsdGeom
import threading # type: ignore
import os


class SphereTransformListenerExtension(omni.ext.IExt):
    def on_startup(self, ext_id):
        logging.warning("SphereTransformListenerExtension: Extension startup.")
        
        self._sphere_path = "/World/Sphere"
        self._stage = omni.usd.get_context().get_stage()

        # Store the initial position of the sphere
        self._last_position = None
        self._polling_active = False  # Control flag for the polling thread
        self._poll_thread = None  # Reference to the polling thread
        self._text_file_path = os.path.join(os.path.expanduser("~/Documents"), "sphere_transform_data.txt")
        self._flag = False


        # Setup UI
        self._window = ui.Window("Location Listener", width=300, height=300)
        with self._window.frame:
            with ui.VStack():
                def add_sphere():
                    logging.warning("Add Sphere button clicked.")
                    if self._stage.GetPrimAtPath(self._sphere_path).IsValid():
                        logging.warning("Sphere already exists.")
                        return
                    omni.kit.commands.execute('CreatePrimWithDefaultXform',
                                              prim_type='Sphere',
                                              attributes={'radius': 50.0})
                    logging.warning("Sphere created.")
                    self._start_transform_polling()

                def delete_sphere():
                    logging.warning("Delete Sphere button clicked.")
                    omni.kit.commands.execute('DeletePrims', paths=[self._sphere_path])
                    logging.warning("Sphere deleted.")
                    self._stop_transform_polling()
                    self._remove_file_if_exists()

                ui.Button("Add avatar", clicked_fn=add_sphere)
                ui.Button("Delete avatar", clicked_fn=delete_sphere)

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
                logging.warning(f"Sphere moved! New position: {position}")
                self._send_data_to_backend(position)


    def _send_data_to_backend(self, position):
        """Writes the sphere's position to a plain text file with three-digit accuracy."""
        # Construct the file path
        directory = os.path.expanduser("~/Documents")  # Use the Documents folder for better accessibility
        text_file_path = os.path.join(directory, "sphere_transform_data.txt")

        try:
            # Format position values to three decimal places
            formatted_position = tuple(round(coord, 3) for coord in position)

            # Open the text file in append mode and write the position
            with open(text_file_path, "a") as file:
                if self._flag == False:
                    file.write(f"Sphere created at position: {formatted_position}\n")
                    self._flag = True
                else:
                    file.write(f"Sphere moved at position: {formatted_position}\n")
            logging.warning(f"Position logged to {text_file_path}: {formatted_position}")
        except PermissionError as e:
            logging.error(f"PermissionError: Unable to write to {text_file_path}. Details: {e}")
        except Exception as e:
            logging.error(f"Unexpected error while writing to {text_file_path}: {e}")
    
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
