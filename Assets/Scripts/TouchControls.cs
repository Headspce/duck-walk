using UnityEngine;

// On-screen touch controls (OnGUI: no UI package needed).
// Hold the < / > buttons to walk the duck left and right.
public class TouchControls : MonoBehaviour
{
    // -1 = walk left, +1 = walk right, 0 = idle. Read by DuckWalker.
    public static float moveInput = 0f;

    void OnGUI()
    {
        float size = 140f;
        float margin = 24f;
        float y = Screen.height - size - margin;

        bool left = GUI.RepeatButton(new Rect(margin, y, size, size), "<");
        bool right = GUI.RepeatButton(new Rect(Screen.width - size - margin, y, size, size), ">");

        moveInput = (right ? 1f : 0f) - (left ? 1f : 0f);

        GUI.Label(new Rect(margin, y - 36f, 320f, 30f), "Hold < or > to walk the duck");
    }
}
