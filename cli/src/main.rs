use std::env;
use std::io::{self, BufRead};
use ffmpeg::FFmpeg;

fn video_to_audio(video_path: &str, output_path: &str) {
    let ffmpeg = FFmpeg::new(video_path).output(output_path).run();
}

fn main() {
    let stdin = io::stdin();
    let mut input = String::new();
    
    println!("Enter video path:");
    stdin.lock().read_line(&mut input).expect("Failed to read input");
    let video_path = input.trim().to_string();
    
    input.clear();
    println!("Enter output path:");
    stdin.lock().read_line(&mut input).expect("Failed to read input");
    let output_path = input.trim().to_string();

    video_to_audio(&video_path, &output_path);
}
