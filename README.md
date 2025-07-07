# DualSense Motion to Key Mapper

This application captures the motion data from a Sony DualSense controller and maps it to custom keyboard and mouse actions. It features a real-time 3D visualizer to help you define motion-based controls. You can record specific controller positions, chain them into complex sequences, and bind these sequences to actions, creating powerful custom controls for games, applications, or accessibility tools.

![3D Visualizer]([(https://i.ibb.co/0Rd3TRnd/Image1.png)])

## Features

* **Real-time 3D Visualization**: A live, interactive 3D view of your controller's orientation and the position of reference points, helping you to visualize your custom motions.
* **Motion Point Capture**: Record the precise 3D position of a "controller tip" to serve as waypoints for your motions.
* **Motion Sequencing with Groups and Chains**:
    * **Groups**: Group multiple motion points together. An action is triggered only when all points in a group have been "hit" within a set grace period.
    * **Chaining**: Define a required order for hitting points by chaining them. A point only becomes active after its parent point has been hit, allowing for complex and deliberate gesture recognition.
* **Action Binding**: Bind completed motion sequences (groups) to a wide variety of actions, including keyboard presses (e.g., `w`, `space`, `ctrl`) and mouse clicks (`left`, `right`).
* **Home Position & Zeroing**: Set a "home" orientation for your controller that you can return to at any time with the press of a button. You can also update this home position and transform all existing points relative to the new orientation.
* **Configuration Management**: Save and load your entire setup—including points, groups, actions, and filter settings—to and from `.json` configuration files.
* **Customizable Sensitivity**: Fine-tune the motion-sensing experience with adjustable settings for hit tolerance, filter gains, and accelerometer smoothing.

## Installation

You can install this application by using the pre-built executable or by running it from the source code.

### From Release (Recommended)

1.  Navigate to the **[Releases](https://github.com/nicholast833/PyDualSense-MotionToKey/releases)** page of this GitHub repository.
2.  Download the `DualSenseMotionToKey.exe` file from the latest release.
3.  The build process automatically includes the required `SDL2.dll` and `hidapi.dll` files. Ensure they remain in the same directory as the executable.
4.  Run the `DualSenseMotionToKey.exe`.

### From Source (Advanced)

This method is for users who want to modify or inspect the code.

1.  **Prerequisites**:
    * Python 3.10 or newer.
    * Git.
    * `SDL2` and `hidapi` libraries. You must download the 64-bit `.dll` files for each and place them in the root directory of the project.
        * **SDL2:** Download from [libsdl.org](https://www.libsdl.org/) (e.g., `SDL2-devel-2.30.2-VC.zip`) and copy `SDL2.dll` from `lib/x64/`.
        * **hidapi:** Download from the [hidapi GitHub](https://github.com/libusb/hidapi/releases) (e.g., `hidapi-win.zip`) and copy `hidapi.dll` from the `x64/` directory.

2.  **Clone the repository:**
    ```bash
    git clone [https://github.com/nicholast833/PyDualSense-MotionToKey.git](https://github.com/nicholast833/PyDualSense-MotionToKey.git)
    cd PyDualSense-MotionToKey
    ```

3.  **Create a virtual environment (recommended):**
    ```bash
    python -m venv venv
    venv\Scripts\activate
    ```

4.  **Install the required Python libraries using the [requirements.txt]() file:**
    ```bash
    pip install -r requirements.txt
    ```

5.  **Run the application:**
    ```bash
    python main_app.py
    ```

## How to Use

Follow these steps to capture a motion and bind it to an action.

1.  **Connect and Calibrate**:
    * Connect your DualSense controller to your PC via Bluetooth or cable.
    * Run the application. The status bar will show "Calibrating...". Keep the controller still on a flat surface until the status changes to "Connected".

2.  **Set a Home Position**:
    * Hold the controller in a comfortable, neutral position.
    * In the **Controller Actions** panel, click **Set Home**. This saves your current orientation as the default "home" you can easily return to.

3.  **Capture a Motion (Record Reference Points)**:
    * The application tracks a virtual "tip" extending from the controller. You will define your motion by recording the positions of this tip.
    * Move the controller so the tip (represented by the small axis crosshair in the visualizer) is where you want your first motion point.
    * In the **Reference Points** panel, click **Record Current Tip Position**. A new point will appear in the 3D view and the points list.
    * Repeat this process to create all the points needed for your gesture.

4.  **Create a Motion Sequence (Group and Chain the Points)**:
    * **Create a Group**: In the **Point Groups & Actions** panel, click **New** to create a group for your sequence. Give it a descriptive name.
    * **Assign Points to the Group**: Select a point in the **Reference Points** list. Then, in the **Edit Selected Point** panel, use the "Assign to Group" dropdown to add it to the group you just created. Repeat for all points in your sequence.
    * **(Optional) Chain the Points**: To force the points to be hit in a specific order, select a point (e.g., your second point) and use the "Chain After Point" dropdown to select its predecessor (e.g., your first point). Chained points will appear purple in the visualizer until their parent point is hit, after which they become active (cyan).

5.  **Bind an Action**:
    * Select your group in the **Point Groups & Actions** list.
    * Under "Selected Group Details", choose an "Action Type" (Key Press or Mouse Click) and enter the "Action Detail" (e.g., `w`, `e`, `left`, `right`).
    * Click **Update Group Details**.

Now, when you move your controller to hit all the points in the group (respecting the chain order if you set one), the bound action will be executed.

## Contributing

Contributions are welcome! If you have suggestions or find a bug, please open an issue or submit a pull request.

## License

This project is licensed under the MIT License. See the `LICENSE.txt` file for more details.
