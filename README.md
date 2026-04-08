# ValidationUtility

A multi-platform utility for validating OpenAPI and AsyncAPI specifications.

## Installation

### Windows
1.  Download the `ValidationUtility-Setup-vX.X.X.exe` installer from the [Releases](link-to-your-releases) page.
2.  Run the installer and follow the on-screen instructions.
3.  The application will be added to your Start Menu and Desktop.

### macOS
1.  Download the `macos-app.zip` (or the `.app` bundle) from the [Releases](link-to-your-releases) page.
2.  Extract the ZIP file.
3.  **Bypassing Security Warning**:
    -   Because the app is not signed with an Apple Developer certificate, macOS will likely block it with a "malware" or "unidentified developer" warning.
    -   **Solution 1 (easiest)**: Right-click (or Control-click) the `ValidationUtility.app` icon and select **Open**. In the dialog that appears, click **Open** again.
    -   **Solution 2 (terminal)**: Open Terminal and run the following command on the extracted app folder:
        ```bash
        xattr -d com.apple.quarantine /path/to/ValidationUtility.app
        ```
    -   **Solution 3**: Go to **System Settings** -> **Privacy & Security**. Scroll down to find the section about the app being blocked and click **Open Anyway**.

## Features
-   Validate OpenAPI (YAML) specs.
-   Validate AsyncAPI (YAML) specs.
-   Auto-fix formatting and naming conventions.
-   Export validation results to CSV.
