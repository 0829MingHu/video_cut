import os
import cv2
import subprocess
import re 
import json 
import webvtt
from concurrent.futures import ThreadPoolExecutor,as_completed

"""
使用前，需要将ffmpeg和ffprobe装好
"""

video_root='./downloads' #视频路径
thread_num=10 #线程数
duration=40 #每段时长，单位秒


class VideoClip:
    
    def get_files(self,dir):
        """
        获取所有的MP4文件
        """
        all_files=[]
        for root,dirs,files in os.walk(dir):
            for file in files:
                if file.endswith('.mp4'):
                    all_files.append(os.path.join(root,file).replace('\\','/'))
        return all_files


    def get_video_duration(self,filename):
        cap = cv2.VideoCapture(filename)
        if cap.isOpened():
            rate = cap.get(5)
            frame_num =cap.get(7)
            duration = round(frame_num/rate,0)
            return duration
        return -1
    
    def get_audio_duration(self,audio_file,audio_type='m4a'):
        cmd='ffprobe -of json -v info -show_format -show_streams %s'%audio_file
        ir=subprocess.Popen(cmd,shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        out,err=ir.communicate()
        data=json.loads(out)
        duration=data['format']['duration']
        return float(duration)

    def extract_action_path(self,file):
        """
        获取family/genus/keyword/action分类
        返回分类路径
        """
        #判断分隔符
        if '/' in file:
            action_path=file.split('/')[-5:-1]
        else:
            action_path=file.split('\\')[-5:-1]
        return '/'.join(action_path)
    
    def split_video(self,source_video,duration,split_num):
        """
        切割视频
        """
        base_cmd="""
        ffmpeg -n -ss {start_time} -t {duration} -i {source_video} -vcodec copy -acodec copy {target_video} -v quiet
        """
        source_duration=self.get_video_duration(source_video)
        if source_duration<duration:
            return
        start_time='00:00:00'
        # split_num=int(source_duration/duration)
        # print('video length: ',source_duration,'video split_num:',split_num)
        for i in range(split_num):
            target_video=source_video.replace('.mp4','_%s.mp4'%i)
            cmd=base_cmd.format(start_time=start_time,duration=duration,source_video=source_video,target_video=target_video)
            os.system(cmd)
            start_time=self.get_time_str(duration,i)
        os.remove(source_video)
    
    def split_audio(self,source_audio,duration,split_num):
        """
        切割音频
        """
        #禁止提示
        base_cmd="""
        ffmpeg -n -ss {start_time} -t {duration} -i {source_audio} -vn {target_audio} -v quiet
        """
        source_duration=self.get_audio_duration(source_audio)
        if source_duration<duration:
            return
        start_time='00:00:00'
        # split_num=int(source_duration/duration)
        # print('audio length: ',source_duration,'audio split_num:',split_num)
        for i in range(split_num):
            target_audio=source_audio.replace('.m4a','_%s.m4a'%i)
            cmd=base_cmd.format(start_time=start_time,duration=duration,source_audio=source_audio,target_audio=target_audio)
            os.system(cmd)
            start_time=self.get_time_str(duration,i)
        os.remove(source_audio)
    
    def split_vtt(self,source_file,duration,split_num):
        """
        切割字幕
        """
        vtt=webvtt.read(source_file)
        source_duration=vtt.total_length
        if source_duration<duration:
            return
        send_time=duration
        i=0
        # split_num=int(source_duration/duration)
        # print('vtt length: ',source_duration,'vtt split_num:',split_num)
        new_captions=[]
        for caption in vtt.captions:
            end_time=self.str_to_int(caption.end)
            # print('end_time: '+str(end_time))
            if end_time<=send_time or (split_num==i):
                # print('append caption ,split_num:',split_num,'i:',i)
                new_captions.append(caption)
            else:
                # print('save_vtt:',i,'split_num:',split_num)
                self.save_vtt(new_captions,source_file.replace('.vtt','_%s.vtt'%i))
                new_captions=[]
                i+=1
                send_time+=duration
                new_captions.append(caption)
        os.remove(source_file)

    def str_to_int(self,duration):
        """
        00:00:10 -> 10
        """
        h=int(duration.split(':')[0])
        m=int(duration.split(':')[1])
        s=int(duration.split(':')[2].split('.')[0])
        return h*3600+m*60+s
    
    def save_vtt(self,captions,filename):
        vtt=webvtt.WebVTT(captions=captions)
        vtt.save(filename)
    
    def get_time_str(self,duration,i):
        """
        获取时间字符串
        """
        h=duration*i//3600
        m=(duration*i-h*3600)//60
        s=(duration*i-h*3600-m*60)
        h=str(h) if h>=10 else '0'+str(h)
        m=str(m) if m>=10 else '0'+str(m)
        s=str(s) if s>=10 else '0'+str(s)
        return '%s:%s:%s'%(h,m,s)
    
    
    def split_all_format_file(self,mp4_file,duration):
        """
        根据视频路径,对相同路径下的mp4、vtt、m4a文件进行切割
        Z_cDpE1xvI4
        """
        #正则匹配YouTube视频ID
        id=re.findall('[a-zA-Z0-9_-]{11}',mp4_file)[0]
        #视频长度
        total_duration=self.get_video_duration(mp4_file)
        #切割份数
        split_num=int(total_duration/duration)
        #切割份数少于2份，就不动了
        if split_num<2:
            print(f'{mp4_file}无需切割')
            return
        #视频路径
        dir_path=os.path.dirname(mp4_file)
        files=os.listdir(dir_path)
        for file in files:
            if id in file:
                if 'vtt' in file:
                    vtt_file=os.path.join(dir_path,file)
                elif 'm4a' in file:
                    m4a_file=os.path.join(dir_path,file)
        # print(os.path.join(dir_path,vtt_file),os.path.join(dir_path,m4a_file))
        # # 移动mp4、vtt、m4a文件
        if vtt_file:
            print(f'切割{vtt_file}')
            self.split_vtt(vtt_file,duration,split_num)
        if m4a_file:
            print(f'切割{m4a_file}')
            self.split_audio(m4a_file,duration,split_num)
        print(f'切割{mp4_file}')
        self.split_video(mp4_file,duration,split_num)
        print(f'{mp4_file}及其相关文件切割成功->{split_num}份')
    
    def main(self,path):
        videos=self.get_files(path)
        with ThreadPoolExecutor(max_workers=thread_num) as t:
            for video in videos:
                t.submit(self.split_all_format_file,video,duration)


if __name__=='__main__':
    VideoClip().main(video_root)