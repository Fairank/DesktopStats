#version 440
layout(location = 0) in vec2 qt_TexCoord0;
layout(location = 0) out vec4 fragColor;
layout(std140, binding = 0) uniform buf {
    mat4 qt_Matrix;
    float qt_Opacity;
    float stagePosition;
    float framePosition;
};
layout(binding = 1) uniform sampler2D source;
vec4 cell(float stage, float frame) {
    return texture(source, (vec2(mod(frame, 48.0), min(9.0, stage)) + qt_TexCoord0) / vec2(48.0, 10.0));
}
void main() {
    float s = floor(stagePosition), f = floor(framePosition);
    float sy = fract(stagePosition), fx = fract(framePosition);
    vec4 a = cell(s, f) * ((1.0-fx)*(1.0-sy)*qt_Opacity);
    vec4 b = cell(s, f+1.0) * (fx*(1.0-sy)*qt_Opacity);
    vec4 c = cell(s+1.0, f) * ((1.0-fx)*sy*qt_Opacity);
    vec4 d = cell(s+1.0, f+1.0) * (fx*sy*qt_Opacity);
    vec4 ab = b + a*(1.0-b.a);
    vec4 abc = c + ab*(1.0-c.a);
    fragColor = d + abc*(1.0-d.a);
}
