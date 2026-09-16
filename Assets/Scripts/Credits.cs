using UnityEngine;

// In-game attribution for the CC-BY-4.0 duck model (OnGUI: no UI package needed).
public class Credits : MonoBehaviour
{
    void OnGUI()
    {
        GUI.Label(new Rect(12, 12, Screen.width - 24, 28),
            "Duck_Walk (Free) by Nyilonelycompany, licensed under CC-BY-4.0");
    }
}
