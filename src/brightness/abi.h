#ifndef X2D_ABI_H
#define X2D_ABI_H
/* Android LP64 declarations used by this freestanding, libc-only extension. */
typedef unsigned long size_t;
typedef long ssize_t;
typedef unsigned long uintptr_t;
typedef unsigned int u32;
typedef unsigned long u64;
extern int open(const char *, int, ...), close(int), unlink(const char *), rename(const char *,const char *), fsync(int);
extern ssize_t read(int, void *, size_t), write(int, const void *, size_t), readlink(const char *,char *,size_t);
extern ssize_t send(int,const void *,size_t,int);
extern int fcntl(int,int,...);
extern int getpid(void);
extern int strcmp(const char *,const char *), strncmp(const char *,const char *,size_t), memcmp(const void *,const void *,size_t);
extern void *memcpy(void *,const void *,size_t), *memset(void *,int,size_t), *dlsym(void *,const char *);
extern void *dlopen(const char *,int);
extern char *getenv(const char *), *strstr(const char *,const char *);
extern int snprintf(char *,size_t,const char *,...), sscanf(const char *,const char *,...);
extern int socket(int,int,int),bind(int,const void *,unsigned),listen(int,int),accept(int,void *,void *),setsockopt(int,int,int,const void *,unsigned);
extern int pthread_create(unsigned long *,const void *,void *(*)(void *),void *), pthread_detach(unsigned long);
extern int pthread_rwlock_init(void *,const void *),pthread_rwlock_rdlock(void *),pthread_rwlock_wrlock(void *),pthread_rwlock_unlock(void *);
extern int pthread_rwlock_tryrdlock(void *);
extern void _exit(int);
struct dl_phdr_info { uintptr_t base; const char *name; const void *phdr; unsigned short phnum; };
extern int dl_iterate_phdr(int (*)(struct dl_phdr_info *,size_t,void *),void *);
#endif
