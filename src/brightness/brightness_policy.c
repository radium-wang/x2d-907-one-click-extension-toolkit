#include "brightness_policy.h"
static int normal(int v){return v<1?1:v>100?100:v;}
void brightness_reset(struct brightness_policy *p,int manual,double now){
 p->filtered=normal(manual);p->target=p->filtered;p->last_time=now;p->initialized=1;
 p->applied=normal(manual);p->effective=0;p->last_eligible=0;
}
int brightness_step(struct brightness_policy *p,int enabled,int valid,double sensor,
                    int eligible,int manual,double now,int *output){
 manual=normal(manual); /* Saved stock slider = automatic ceiling and manual fallback. */
 if(!p->initialized)brightness_reset(p,manual,now);
 if(!eligible){p->effective=0;p->last_eligible=0;p->last_time=now;return 0;}
 if(!p->last_eligible){p->filtered=p->applied;p->last_time=now;}
 p->last_eligible=1;
 if(!enabled||!valid){
  p->effective=0;p->filtered=manual;p->target=manual;p->last_time=now;
  if(p->applied==manual)return 0;
  p->applied=manual;*output=manual;return 1;
 }
 double target=sensor<=10?5:sensor>=450?100:5+(sensor-10)*95/440;
 if(target>manual)target=manual;
 double change=target-p->target;if(change<0)change=-change;
 if(change>=1.98||target==5||target==manual)p->target=target;
 if(p->target>manual)p->target=manual;
 target=p->target;
 double dt=now-p->last_time;p->last_time=now;
 if(dt<0||dt>1){p->filtered=p->applied;dt=0;}
 if(p->filtered>manual)p->filtered=manual;
 /* Bounded, evenly paced transitions avoid the exponential filter's long tail
    of isolated 1% dimming steps. Stock output still has integer percent precision. */
 double delta=target-p->filtered,step=dt*(delta>0?80.:24.);
 if(delta>step)delta=step;else if(delta<-step)delta=-step;
 p->filtered+=delta;
 int value=normal((int)(p->filtered+.5));
 p->effective=1;
 if(value!=p->applied){p->applied=value;*output=value;return 1;}
 return 0;
}
