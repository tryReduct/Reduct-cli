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
