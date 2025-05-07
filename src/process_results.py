from typing import List, Dict
from twelve import search_video, client, INDEX_ID

class ClipProcessor:
    def __init__(self):
        self.processed_clips: List[Dict] = []
        
    def get_highest_scored_clips(self, query: str, min_score: float = 0.7, video_id: str = None) -> List[Dict]:
        """
        Get clips with the highest scores from the search results.
        
        Args:
            query (str): The search query
            min_score (float): Minimum score threshold (default: 0.7)
            video_id (str, optional): If provided, only return clips from this video ID
            
        Returns:
            List[Dict]: List of processed clips with their details
        """
        # Reset processed clips list
        self.processed_clips = []
        
        # Get search results
        search_params = {
            "index_id": INDEX_ID,
            "options": ["visual", "audio"],
            "query_text": query,
            "group_by": "clip",
            "operator": "or",
            "page_limit": 5,
            "sort_option": "score",
        }
        
        # Add video_id filter if provided
        if video_id:
            search_params["video_id"] = video_id
        
        result = client.search.query(**search_params)
        
        # Process and store clips
        for item in result.data:
            if hasattr(item, 'clips'):  # GroupByVideoSearchData
                for clip in item.clips:
                    if clip.score >= min_score:
                        self.processed_clips.append({
                            'video_id': clip.video_id,
                            'start_time': clip.start,
                            'end_time': clip.end,
                            'score': clip.score,
                            'thumbnail_url': clip.thumbnail_url
                        })
            else:  # Regular SearchData
                if item.score >= min_score:
                    self.processed_clips.append({
                        'video_id': item.video_id,
                        'start_time': item.start,
                        'end_time': item.end,
                        'score': item.score,
                        'thumbnail_url': item.thumbnail_url
                    })
        
        # Sort by score in descending order
        self.processed_clips.sort(key=lambda x: x['score'], reverse=True)
        return self.processed_clips
    
    def get_top_clip(self) -> Dict:
        """
        Get the clip with the highest score.
        
        Returns:
            Dict: The highest scored clip details
        """
        if not self.processed_clips:
            return None
        return self.processed_clips[0]

def main():
    processor = ClipProcessor()
    
    while True:
        print("\nClip Processing Menu")
        print("1. Search and process clips")
        print("2. Show top clip")
        print("3. Show all processed clips")
        print("4. Exit")
        
        choice = input("Enter your choice (1-4): ").strip()
        
        if choice == "1":
            query = input("Enter your search query: ")
            clips = processor.get_highest_scored_clips(query)
            print(f"\nFound {len(clips)} clips with score >= 0.7")
            
        elif choice == "2":
            top_clip = processor.get_top_clip()
            if top_clip:
                print("\nTop Clip Details:")
                print(f"Video ID: {top_clip['video_id']}")
                print(f"Time Range: {top_clip['start_time']} - {top_clip['end_time']}")
                print(f"Score: {top_clip['score']}")
            else:
                print("No clips processed yet.")
                
        elif choice == "3":
            if processor.processed_clips:
                print("\nAll Processed Clips:")
                for i, clip in enumerate(processor.processed_clips, 1):
                    print(f"\nClip {i}:")
                    print(f"Video ID: {clip['video_id']}")
                    print(f"Time Range: {clip['start_time']} - {clip['end_time']}")
                    print(f"Score: {clip['score']}")
            else:
                print("No clips processed yet.")
                
        elif choice == "4":
            print("Goodbye!")
            break
            
        else:
            print("Invalid choice. Please try again.")

if __name__ == "__main__":
    main() 