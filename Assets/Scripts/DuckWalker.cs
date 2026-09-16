using UnityEngine;

// Moves the duck across the screen and wraps it around.
// Also guarantees the imported walk clip loops: the FBX .meta requests the
// Legacy animation type, and as a safety net we force the legacy flag and
// loop wrap mode here in case the .meta was not honoured on import.
[RequireComponent(typeof(Animation))]
public class DuckWalker : MonoBehaviour
{
    public float speed = 1.2f;
    public float minX = -5f;
    public float maxX = 5f;

    private Animation anim;

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
        if (anim.clip != null && !anim.isPlaying)
            anim.Play();
    }

    void Update()
    {
        transform.position += Vector3.right * speed * Time.deltaTime;
        if (transform.position.x > maxX)
        {
            Vector3 p = transform.position;
            p.x = minX;
            transform.position = p;
        }
        if (anim != null && anim.clip != null && !anim.isPlaying)
            anim.Play();
    }
}
