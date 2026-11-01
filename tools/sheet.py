import subprocess,sys
names=sys.argv[3].split(',')
d=sys.argv[1]; out=sys.argv[2]; at=sys.argv[4]
inputs=[];fc=[]
cols=4; W,H=480,270
for i,n in enumerate(names):
    inputs+=['-i',f'{d}/{n}/f{int(at):05d}.jpg']
    fc.append(f"[{i}:v]scale={W}:{H},drawtext=text='{n}':x=6:y=6:fontsize=16:fontcolor=white:box=1:boxcolor=black@0.6:fontfile='C\\:/Windows/Fonts/consola.ttf'[v{i}]")
lay='|'.join(f'{(i%cols)*W}_{(i//cols)*H}' for i in range(len(names)))
f=';'.join(fc)+';'+''.join(f'[v{i}]' for i in range(len(names)))+f'xstack=inputs={len(names)}:fill=black:layout={lay}[o]'
subprocess.check_call(['ffmpeg','-v','error','-y',*inputs,'-filter_complex',f,'-map','[o]','-frames:v','1',out])
