using UnityEngine;

// Player-controlled duck: the on-screen touch buttons (TouchControls.moveInput)
// drive left/right movement. The walk clip plays while moving, the duck faces
// its travel direction, and it wraps around the screen edges.
// The FBX .meta requests the Legacy animation type, and as a safety net we
// force the legacy flag and loop wrap mode here in case the .meta was not
// honoured on import.
[RequireComponent(typeof(Animation))]
public class DuckWalker : MonoBehaviour
{
    public float speed = 1.2f;
    public float minX = -5f;
    public float maxX = 5f;
    public float turnSpeed = 10f; // how quickly the duck turns around
    public float accel = 8f;      // how quickly it speeds up / slows down

    private Animation anim;
    private float velocity; // smoothed -1..1 drive signal

    void Start()
    {
        anim = GetComponent<Animation>();
        foreach (AnimationState s in anim)
        {
            if (s.clip != null)
            {
                s.clip.legacy = true;   // safety net for the .meta's Legacy flag
                s.wrapMode = WrapMode.Loop;
            }
        }
        anim.wrapMode = WrapMode.Loop;
    }

    void Update()
    {
        float input = TouchControls.moveInput;

        // Ease toward the target direction instead of jumping to full speed:
        // abrupt starts, stops, and direction flips read as jitter.
        velocity = Mathf.MoveTowards(velocity, input, accel * Time.deltaTime);

        if (Mathf.Abs(velocity) > 0.01f)
        {
            transform.position += Vector3.right * velocity * speed * Time.deltaTime;

            // Turn smoothly instead of snapping 180 degrees instantly.
            float targetY = velocity > 0f ? 90f : -90f;
            transform.rotation = Quaternion.Slerp(
                transform.rotation,
                Quaternion.Euler(0f, targetY, 0f),
                Mathf.Clamp01(turnSpeed * Time.deltaTime));

            if (anim != null && anim.clip != null && !anim.isPlaying)
                anim.Play();
        }
        else if (anim != null && anim.isPlaying)
        {
            anim.Stop();
        }

        Vector3 p = transform.position;
        if (p.x > maxX) p.x = minX;
        else if (p.x < minX) p.x = maxX;
        transform.position = p;
    }
}
