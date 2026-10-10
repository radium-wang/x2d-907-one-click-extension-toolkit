// First-generation X2D 4.2.0, dynamic still scan multipliers user-selectable Low / Medium / High.
// Preserve stock divisor selection, FPS adjustment, fallback, and 21844 clamp.
.text
.Ldispatch:
.org 0xdc
b .Lbounded
.org 0x13c
and w8,w21,#0xffff
cmp w8,#2
b.hi .Ldispatch+0xc4
fmov s0,#__TYPE0__
fmov s1,#__TYPE1__
cmp w8,#1
fcsel s0,s1,s0,eq
fmov s1,#__TYPE2__
cmp w8,#2
fcsel s0,s1,s0,eq
fmul s10,s10,s0
b .Ldispatch+0xc4
.Lbounded:
fcvtzs w8,s0
and w9,w21,#0xffff
cmp w9,#2
b.hi .Ldispatch+0xe0
ldr w9,[x24,#4]
cmp w9,#2
b.ne .Ldispatch+0xe0
cmp w8,#0
csel w8,wzr,w8,lt
mov w9,#21844
cmp w8,w9
csel w8,w9,w8,hi
b .Ldispatch+0xe0
