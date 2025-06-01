import torch
from torch.utils.data import Dataset, DataLoader
import numpy as np

# 1. Load the saved list of (token_seq, genre_id) pairs
dataset_all = torch.load("midi_token_dataset.pt")  # [(List[int], int), …]

# 2. (Optional) Shuffle and split into train/validation
np.random.shuffle(dataset_all)
n = len(dataset_all)
split_idx = int(n * 0.9)
train_list = dataset_all[:split_idx]
val_list   = dataset_all[split_idx:]

# 3. Define a Dataset that returns (input_window, target_window, genre_id)
class MIDITokenDataset(Dataset):
    def __init__(self, data_list, seq_len=50):
        """
        data_list: list of (token_seq: List[int], genre_id: int)
        seq_len: length of each input sequence (targets are shifted by 1)
        """
        self.data_list = data_list
        self.seq_len = seq_len

    def __len__(self):
        return len(self.data_list)

    def __getitem__(self, idx):
        token_seq, genre_id = self.data_list[idx]
        L = len(token_seq)
        if L <= self.seq_len:
            # pad to (seq_len + 1) so we can split into x and y
            pad = [0] * (self.seq_len + 1 - L)
            seq = pad + token_seq
        else:
            # randomly sample a contiguous window of length (seq_len + 1)
            start = np.random.randint(0, L - self.seq_len)
            seq = token_seq[start : start + self.seq_len + 1]

        seq = np.array(seq, dtype=np.int64)
        x = torch.from_numpy(seq[:-1])  # (seq_len,)
        y = torch.from_numpy(seq[1:])   # (seq_len,)
        return x, y, torch.tensor(genre_id, dtype=torch.long)

# 4. Create DataLoaders
batch_size = 32

train_ds = MIDITokenDataset(train_list, seq_len=50)
val_ds   = MIDITokenDataset(val_list, seq_len=50)

train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True,  drop_last=True)
val_loader   = DataLoader(val_ds,   batch_size=batch_size, shuffle=False, drop_last=True)

print(f"Train batches: {len(train_loader)}, Val batches: {len(val_loader)}")
