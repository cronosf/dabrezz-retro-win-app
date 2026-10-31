"""Aplica a la shell de OpenBIOS (nugget/shell/main.c y Makefile) el cambio que reemplaza el cubo 3D por el logo de Dabrezz Play girando en 3D.
Es idempotente. Uso:  python tools/openbios/patch_shell.py <carpeta nugget/shell>   (lo llama tools/openbios/build.ps1)

Cambios: el fondo pasa al morado de la app; el logo (textura de 8 bits en la VRAM, a la derecha del cuadro de pantalla) se dibuja como un cuadrilatero
texturizado que gira sobre su eje vertical con perspectiva (como el cubo original), con un ligero cabeceo, sombreado segun el angulo y la misma cara
en el reverso (no sale al reves). Aparece haciendose grande en el primer segundo y se apaga cuando arranca el disco; el fogonazo blanco del final pasa
a negro. Se mantienen la deteccion del disco, los sonidos y los tiempos de la shell original (MIT, © PCSX-Redux authors)."""
import os
import sys

d = sys.argv[1]
mk0 = os.path.join(d, "Makefile")
m0 = open(mk0, encoding="utf-8", newline="").read()
if "logo_data.c" not in m0:                       # el Makefile se parchea siempre, aunque main.c ya estuviera aplicado
    nl0 = "\r\n" if "\r\n" in m0 else "\n"
    open(mk0, "w", encoding="utf-8", newline="").write(m0.replace("hull.c \\" + nl0, "hull.c \\" + nl0 + "logo_data.c \\" + nl0, 1))
p = os.path.join(d, "main.c")
s = open(p, encoding="utf-8", newline="").read().replace("\r\n", "\n")
if "LOGO_W" in s:
    print("ya aplicado")
    sys.exit(0)


def rep(a, b):
    global s
    assert a in s, a[:60]
    s = s.replace(a, b, 1)


rep('#include "shell/hull.h"\n', '#include "shell/hull.h"\n#include "shell/logo.h"\n')
rep("static const union Color c_bgIdle = {.r = 0, .g = 64, .b = 91};", "static const union Color c_bgIdle = {.r = LOGO_BG_R, .g = LOGO_BG_G, .b = LOGO_BG_B};")
rep("static const union Color c_bgSuccess = {.r = 36, .g = 91, .b = 0};", "static const union Color c_bgSuccess = {.r = LOGO_BG_R, .g = LOGO_BG_G, .b = LOGO_BG_B};")
rep("            s_lerps[0].c.d = c_white;\n            s_lerps[1].c.d = c_white;\n            s_lerps[2].c.d = c_white;\n",
    "            s_lerps[0].c.d = c_black;\n            s_lerps[1].c.d = c_black;\n            s_lerps[2].c.d = c_black;\n")
i = s.index("static void render() {")
j = s.index("static int s_bootFrames = 0;\n") + len("static int s_bootFrames = 0;\n")
new = r'''// ---- Dabrezz Play: logo de arranque girando en 3D en lugar del cubo ----
static void uploadLogo() {
    // paleta (256 entradas de 15 bits) y textura de 8 bits: se copian a la VRAM fuera del cuadro de pantalla.
    // Como GPU_dw del propio OpenBIOS: se espera una vez antes del comando y los datos se escriben sin esperar (durante la copia el bit 26 del estado
    // de la GPU no vuelve a 1 hasta que termina, y esperarlo palabra a palabra deja la shell colgada).
    waitGPU();
    GPU_DATA = 0xa0000000;
    GPU_DATA = (LOGO_CLUT_Y << 16) | LOGO_CLUT_X;
    GPU_DATA = (1 << 16) | 256;
    for (unsigned i = 0; i < 128; i++) GPU_DATA = g_logoClut[i];
    waitGPU();
    GPU_DATA = 0xa0000000;
    GPU_DATA = (LOGO_TEX_Y << 16) | LOGO_TEX_X;
    GPU_DATA = (LOGO_H << 16) | (LOGO_W / 2);
    for (unsigned i = 0; i < LOGO_H * (LOGO_W / 4); i++) GPU_DATA = g_logoPixels[i];
    waitGPU();
}

static int s_scheduleBoot = 0;
static int s_bootFrames = 0;

// brillo del logo (128 = normal): aparece en el primer segundo y se apaga mientras arranca el disco
static unsigned logoLevel() {
    unsigned fps = s_FPS ? s_FPS : 60;
    unsigned level = 128;
    if (s_phase == 0) level = s_frameCounter * 128 / fps;
    if (s_bootFrames > (int)(fps * 2)) {
        unsigned done = s_bootFrames - fps * 2;
        level = done >= fps * 2 ? 0 : level * (fps * 2 - done) / (fps * 2);
    }
    return level > 128 ? 128 : level;
}

static inline uint32_t gpuPoint(int x, int y) { return ((uint32_t)(uint16_t)x) | ((uint32_t)y << 16); }

static void render() {
    unsigned level = logoLevel();
    if (level == 0) return;
    unsigned fps = s_FPS ? s_FPS : 60;
    unsigned counter = s_frameCounter;

    // giro: una vuelta cada 2,5 s sobre el eje vertical y un leve cabeceo; al arrancar el disco gira mas rapido
    unsigned turn = s_bootFrames > 0 ? 3 : 2;
    int yAngle = (int)((counter * 2048u * turn) / (fps * 5u)) & 2047;
    int xAngle = (int)((dSin((counter * 7u) & 2047) * 70) >> 24);
    struct Matrix3D m, rx;
    generateRotationMatrix3D(&m, yAngle, AXIS_Y);
    generateRotationMatrix3D(&rx, xAngle, AXIS_X);
    multiplyMatrix3D(&m, &rx, &m);
    int32_t scale = s_phase == 0 ? lerpD(ONE / 5, ONE, counter * ONE / fps) : ONE;       // entra creciendo
    scaleMatrix3D(&m, scale);

    // las cuatro esquinas del cartel (560x326 px a escala 1) giradas y con perspectiva
    const int32_t hw = 280 << 17, hh = 163 << 17;
    const struct Vertex3D corner[4] = {{-hw, -hh, 0}, {hw, -hh, 0}, {-hw, hh, 0}, {hw, hh, 0}};
    const int32_t F2 = 9 * ONE;
    int px[4], py[4];
    for (int k = 0; k < 4; k++) {
        struct Vertex3D out;
        matrixVertexMul3D(&m, &corner[k], &out);
        int32_t dd = dDiv(F2, F2 + ONE - out.z);
        px[k] = WIDTH / 2 + (dMul(out.x, dd) >> 17);
        py[k] = HEIGHT / 2 + (dMul(out.y, dd) >> 17);
    }
    // de espaldas el cartel mostraria el logo al reves: se invierte la textura para que siempre se lea bien
    int cross = (px[1] - px[0]) * (py[2] - py[0]) - (py[1] - py[0]) * (px[2] - px[0]);
    unsigned uL = cross >= 0 ? 0 : LOGO_W - 1, uR = cross >= 0 ? LOGO_W - 1 : 0;

    // sombreado: mas oscuro cuando esta de canto
    int c = dCos(yAngle);
    if (c < 0) c = -c;
    unsigned shade = level * (96 + (unsigned)(c >> 19)) / 128;     // c>>19 = 0..32
    if (shade > 128) shade = 128;

    const uint32_t clut = ((LOGO_CLUT_Y << 6) | (LOGO_CLUT_X >> 4)) << 16;
    const uint32_t tpage = ((LOGO_TEX_X / 64) | ((LOGO_TEX_Y / 256) << 4) | (1 << 7)) << 16;     // 8 bits por texel
    const uint32_t vmax = (LOGO_H - 1) << 8;
    // cuadrilatero texturizado, modulado por el brillo. Solo la palabra de comando espera a la GPU: el resto son sus parametros (si se esperara el
    // bit 26 en cada uno, la GPU, que esta esperando parametros, no lo pone a 1 y la shell se cuelga)
    sendGPUData(0x2c000000 | (shade << 16) | (shade << 8) | shade);
    GPU_DATA = gpuPoint(px[0], py[0]); GPU_DATA = clut | uL;
    GPU_DATA = gpuPoint(px[1], py[1]); GPU_DATA = tpage | uR;
    GPU_DATA = gpuPoint(px[2], py[2]); GPU_DATA = vmax | uL;
    GPU_DATA = gpuPoint(px[3], py[3]); GPU_DATA = vmax | uR;
}
'''
s = s[:i] + new + s[j:]
rep("    initGPU(isPAL);\n", "    initGPU(isPAL);\n    uploadLogo();\n")
open(p, "w", encoding="utf-8", newline="").write(s)
print("aplicado")
