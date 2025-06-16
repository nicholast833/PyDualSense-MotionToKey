# PyDualSense-MotionToKey

This project is a Python-based application that allows you to capture and map motion data from a Sony DualSense controller to custom actions. You can save specific controller positions and create complex motion sequences, which can then be bound to keyboard presses or mouse clicks. This is useful for creating custom controls for games, applications, or accessibility tools.

## Features

* **Real-time Data Display**: View live gyroscope and accelerometer data from your DualSense controller.
* **Position Saving**: Record and save specific controller orientations as "positions."
* **Motion Sequences**: Chain saved positions together to create complex motion gestures.
* **Action Binding**: Bind completed motion sequences to keyboard keys or mouse clicks.
* **Configuration Management**: Export and import your saved positions and motion sequences to a `.cfg` file.
* **Customizable Smoothing and Padding**: Fine-tune the sensitivity of motion detection.

## Requirements

* Python 3.x
* A Sony DualSense Controller
* A Bluetooth-enabled PC

## Installation

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/your-username/your-repository-name.git](https://github.com/your-username/your-repository-name.git)
    cd your-repository-name
    ```

2.  **Install the required Python libraries:**
    It's recommended to use a virtual environment.
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    pip install -r requirements.txt
    ```

## How to Run

1.  **Connect your DualSense Controller** to your computer via Bluetooth.
2.  **Run the application:**
    ```bash
    python pythonProject/main_app.py
    ```

## How to Use

* **Saving a Position**: Hold your controller in the desired position and click the "Save Current Position (Multi-Point)" button.
* **Creating a Motion Sequence**:
    1.  Go to the "Motions" tab and click "Create New Motion Sequence."
    2.  Give the sequence a name.
    3.  Click the "Edit Positions" button to add saved positions to the sequence.
* **Binding an Action**: Select a motion sequence and enter a key (e.g., `w`, `space`, `ctrl`) or mouse click (`left_click`, `right_click`) in the "Action Binding" field.

## Contributing

Contributions are welcome! If you have suggestions or find a bug, please open an issue or submit a pull request.

## License

This project is licensed under the MIT License. See the `LICENSE` file for more details.
