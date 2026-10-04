/* Small SHA-256 file checker; no crypto library or shell dependency. */
#include "sha256.h"
#ifdef __APPLE__
#include <fcntl.h>
#else
#define O_NOFOLLOW 0x20000
#define O_CLOEXEC 0x80000
#endif
static const u32 k[64]={
0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2};
static u32 rr(u32 x,int n){return (x>>n)|(x<<(32-n));}
static void block(u32 h[8],const unsigned char b[64]){
 u32 w[64];for(int i=0;i<16;i++) w[i]=((u32)b[i*4]<<24)|((u32)b[i*4+1]<<16)|((u32)b[i*4+2]<<8)|b[i*4+3];
 for(int i=16;i<64;i++){u32 x=w[i-15],y=w[i-2];w[i]=w[i-16]+(rr(x,7)^rr(x,18)^(x>>3))+w[i-7]+(rr(y,17)^rr(y,19)^(y>>10));}
 u32 a=h[0],c=h[2],b0=h[1],d=h[3],e=h[4],f=h[5],g=h[6],h0=h[7];
 for(int i=0;i<64;i++){u32 t=h0+(rr(e,6)^rr(e,11)^rr(e,25))+((e&f)^(~e&g))+k[i]+w[i];u32 s=(rr(a,2)^rr(a,13)^rr(a,22))+((a&b0)^(a&c)^(b0&c));h0=g;g=f;f=e;e=d+t;d=c;c=b0;b0=a;a=t+s;}
 h[0]+=a;h[1]+=b0;h[2]+=c;h[3]+=d;h[4]+=e;h[5]+=f;h[6]+=g;h[7]+=h0;
}
int x2d_hash_file(const char *path,const char *expected){
 int fd=open(path,O_NOFOLLOW|O_CLOEXEC);if(fd<0)return 0;
 u32 h[8]={0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19};
 unsigned char data[4096],tail[128];size_t used=0;u64 bytes=0;ssize_t n;
 while((n=read(fd,data,sizeof(data)))>0){bytes+=(u64)n;for(ssize_t j=0;j<n;j++){tail[used++]=data[j];if(used==64){block(h,tail);used=0;}}}
 close(fd);if(n<0)return 0;
 tail[used++]=128;if(used>56){while(used<64)tail[used++]=0;block(h,tail);used=0;}
 while(used<56)tail[used++]=0;for(int i=7;i>=0;i--)tail[used++]=(unsigned char)((bytes*8)>>(i*8));block(h,tail);
 char hex[65];const char *digits="0123456789abcdef";for(int i=0;i<32;i++){unsigned char v=(h[i/4]>>(24-8*(i%4)))&255;hex[2*i]=digits[v>>4];hex[2*i+1]=digits[v&15];}hex[64]=0;
 return !strcmp(hex,expected);
}
