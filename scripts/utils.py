import urllib.request
import os

downloads = {
    "https://engineering.case.edu/sites/default/files/97.mat": "normal_0hp.mat",
    "https://engineering.case.edu/sites/default/files/98.mat": "normal_1hp.mat",
    "https://engineering.case.edu/sites/default/files/99.mat": "normal_2hp.mat",
    "https://engineering.case.edu/sites/default/files/100.mat": "normal_3hp.mat",
    "https://engineering.case.edu/sites/default/files/105.mat": "inner_race_007_0hp.mat",
    "https://engineering.case.edu/sites/default/files/106.mat": "inner_race_007_1hp.mat",
    "https://engineering.case.edu/sites/default/files/107.mat": "inner_race_007_2hp.mat",
    "https://engineering.case.edu/sites/default/files/108.mat": "inner_race_007_3hp.mat",
    "https://engineering.case.edu/sites/default/files/118.mat": "ball_007_0hp.mat",
    "https://engineering.case.edu/sites/default/files/119.mat": "ball_007_1hp.mat",
    "https://engineering.case.edu/sites/default/files/120.mat": "ball_007_2hp.mat",
    "https://engineering.case.edu/sites/default/files/121.mat": "ball_007_3hp.mat",
    "https://engineering.case.edu/sites/default/files/130.mat": "outer_race_007_0hp.mat",
    "https://engineering.case.edu/sites/default/files/131.mat": "outer_race_007_1hp.mat",
    "https://engineering.case.edu/sites/default/files/132.mat": "outer_race_007_2hp.mat",
    "https://engineering.case.edu/sites/default/files/133.mat": "outer_race_007_3hp.mat",
    "https://engineering.case.edu/sites/default/files/209.mat": "inner_race_021_0hp.mat",
    "https://engineering.case.edu/sites/default/files/210.mat": "inner_race_021_1hp.mat",
    "https://engineering.case.edu/sites/default/files/211.mat": "inner_race_021_2hp.mat",
    "https://engineering.case.edu/sites/default/files/212.mat": "inner_race_021_3hp.mat",
    "https://engineering.case.edu/sites/default/files/222.mat": "ball_021_0hp.mat",
    "https://engineering.case.edu/sites/default/files/223.mat": "ball_021_1hp.mat",
    "https://engineering.case.edu/sites/default/files/224.mat": "ball_021_2hp.mat",
    "https://engineering.case.edu/sites/default/files/225.mat": "ball_021_3hp.mat",
    "https://engineering.case.edu/sites/default/files/234.mat": "outer_race_021_0hp.mat",
    "https://engineering.case.edu/sites/default/files/235.mat": "outer_race_021_1hp.mat",
    "https://engineering.case.edu/sites/default/files/236.mat": "outer_race_021_2hp.mat",
    "https://engineering.case.edu/sites/default/files/237.mat": "outer_race_021_3hp.mat",
}

for url, custom_filename in downloads.items():
    print(f"Downloading {url} and saving as {custom_filename}...")
    urllib.request.urlretrieve(url, custom_filename)
print("All downloads complete!")