
def outputTrajectory(frames, filename):
    with open(filename, 'w') as f:
        for frame in frames:
            filename = f'Query_{str(frame.id).zfill(8)}.jpg'
            Twc = frame.Twc
            data_str = ''
            for i in range(4):
                for j in range(4):
                    data_str += f' {Twc[i][j]}'

            f.write(f'{filename} {data_str}\n')