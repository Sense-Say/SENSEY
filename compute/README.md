TRIAL 5
```text
LSLE = Left Elbow - Left Shoulder
LSLE = (Left Elbow.X - Left Shoulder.X , Left Elbow.Y - Left Shoulder.Y , Left Elbow.Z - Left Shoulder.Z)
LSLE = (-0.297 - -0.0545 , 0.4251 - 0.3979 , 1.5534 - 1.577)
LSLE = (-0.2425 , 0.0272 , -0.0236)

SSSB = Spine Base - Spine Shoulder
SSSB = (Spine Base.X - Spine Shoulder.X , Spine Base.Y - Spine Shoulder.Y , Spine Base.Z - Spine Shoulder.Z)
SSSB = (0.1115 - 0.1232 , 0.4169 - -0.1515 , 1.5795 - 1.5372)
SSSB = (-0.0117 , 0.5684 , 0.0423)

LSRE = Reference Elbow - Left Shoulder
LSRE = (Reference Elbow.X - Left Shoulder.X , Reference Elbow.Y - Left Shoulder.Y , Reference Elbow.Z - Left Shoulder.Z)
LSRE = (-0.297 - -0.0545 , 0.4251 - 0.3979 , 1.5534 - 1.5534)
LSRE = (-0.2425 , 0.0272 , 0)

LELS = Left Shoulder - Left Elbow
LELS = (Left Shoulder.X - Left Elbow.X , Left Shoulder.Y - Left Elbow.Y , Left Shoulder.Z - Left Elbow.Z)
LELS = (-0.0545 - -0.297 , 0.3979 - 0.4251 , 1.577 - 1.5534)
LELS = (0.2425 , -0.0272 , 0.0236)

LELW = Left Wrist - Left Elbow
LELW = (Left Wrist.X - Left Elbow.X , Left Wrist.Y - Left Elbow.Y , Left Wrist.Z - Left Elbow.Z)
LELW = (-0.3042 - -0.297 , 0.5881 - 0.4251 , 1.4174 - 1.5534)
LELW = (-0.0072 , 0.163 , -0.136)

SBSS = Spine Shoulder - Spine Base
SBSS = (Spine Shoulder.X - Spine Base.X , Spine Shoulder.Y - Spine Base.Y , Spine Shoulder.Z - Spine Base.Z)
SBSS = (0.1232 - 0.1115 , -0.1515 - 0.4169 , 1.5372 - 1.5795)
SBSS = (-0.0117 , 0.5684 , 0.0423)

n-LELS-LELW = LELS x LELW
n-LELS-LELW = (LELS.Y * LELW.Z - LELS.Z * LELW.Y , LELS.Z * LELW.X - LELS.X * LELW.Z , LELS.X * LELW.Y - LELS.Y * LELW.X)
n-LELS-LELW = (-0.0272 * -0.136 - 0.0236 * 0.163 , 0.0236 * -0.0072 - 0.2425 * -0.136 , 0.2425 * 0.163 - -0.0272 * -0.0072)
n-LELS-LELW = (-0.0001476 , 0.03281008 , 0.03933166)

n-LELS-SBSS = LELS x SBSS
n-LELS-SBSS = (LELS.Y * SBSS.Z - LELS.Z * SBSS.Y , LELS.Z * SBSS.X - LELS.X * SBSS.Z , LELS.X * SBSS.Y - LELS.Y * SBSS.X)
n-LELS-SBSS = (-0.0272 * 0.0423 - 0.0236 * 0.5684 , 0.0236 * -0.0117 - 0.2425 * 0.0423 , 0.2425 * 0.5684 - -0.0272 * -0.0117)
n-LELS-SBSS = (-0.0145648 , -0.01053387 , 0.13751876)

Flexion Angle = COS^-1((SSSB.X*LSRE.X+SSSB.Y*LSRE.Y+SSSB.Z*LSRE.Z)/((SQRT(SSSB.X*SSSB.X+SSSB.Y*SSSB.Y+SSSB.Z*SSSB.Z))*(SQRT(LSRE.X*LSRE.X+LSRE.Y*LSRE.Y+LSRE.Z*LSRE.Z))))
Flexion Angle = COS^-1((-0.0117 * -0.2425 + 0.5684 * 0.0272 + 0.0423 * 0) / (SQRT(-0.0117 * -0.0117 + 0.5684 * 0.5684 + 0.0423 * 0.0423) * SQRT(-0.2425 * -0.2425 + 0.0272 * 0.0272 + 0 * 0)))
Flexion Angle = 97.11012206
Flexion Angle Error = 0.01832206317

Abduction Angle Sign = if LE.Z<ER.Z,-1 | if LE.Z>=ER.Z,1
Abduction Angle Sign = -1
Abduction Angle = 90 + COS^-1((LSLE.X*LSRE.X+LSLE.Y*LSRE.Y+LSLE.Z*LSRE.Z)/((SQRT(LSLE.X*LSLE.X+LSLE.Y*LSLE.Y+LSLE.Z*LSLE.Z))*(SQRT(LSRE.X*LSRE.X+LSRE.Y*LSRE.Y+LSRE.Z*LSRE.Z))))
Abduction Angle = 90 + COS^-1((-0.2425 * -0.2425 + 0.0272 * 0.0272 + -0.0236 * 0) / (SQRT(-0.2425 * -0.2425 + 0.0272 * 0.0272 + -0.0236 * -0.0236) * SQRT(-0.2425 * -0.2425 + 0.0272 * 0.0272 + 0 * 0)))
Abduction Angle = 84.4759268574517
Abduction Angle Error = 0.002573142548

Rotation Angle = COS^-1((n-LELS-LELW.X*n-LELS-SBSS.X+n-LELS-LELW.Y*n-LELS-SBSS.Y+n-LELS-LELW.Z*n-LELS-SBSS.Z)/((SQRT(n-LELS-LELW.X*n-LELS-LELW.X+n-LELS-LELW.Y*n-LELS-LELW.Y+n-LELS-LELW.Z*n-LELS-LELW.Z))*(SQRT(n-LELS-SBSS.X*n-LELS-SBSS.X+n-LELS-SBSS.Y*n-LELS-SBSS.Y+n-LELS-SBSS.Z*n-LELS-SBSS.Z))))
Rotation Angle = COS^-1((-0.0001476 * -0.0145648 + 0.03281008 * -0.01053387 + 0.03933166 * 0.13751876) / (SQRT(-0.0001476 * -0.0001476 + 0.03281008 * 0.03281008 + 0.03933166 * 0.03933166) * SQRT(-0.0145648 * -0.0145648 + -0.01053387 * -0.01053387 + 0.13751876 * 0.13751876)))
Rotation Angle = 44.51500768
Rotation Angle Error = 0.01780768009
```


TRIAL 4
```text
LSLE = Left Elbow - Left Shoulder
LSLE = (Left Elbow.X - Left Shoulder.X , Left Elbow.Y - Left Shoulder.Y , Left Elbow.Z - Left Shoulder.Z)
LSLE = (-0.1098 - -0.0419 , 0.6285 - 0.4528 , 1.5394 - 1.5734)
LSLE = (-0.0679 , 0.1757 , -0.0339999999999998)

SSSB = Spine Base - Spine Shoulder
SSSB = (Spine Base.X - Spine Shoulder.X , Spine Base.Y - Spine Shoulder.Y , Spine Base.Z - Spine Shoulder.Z)
SSSB = (0.1092 - 0.1116 , 0.4277 - -0.1217 , 1.5926 - 1.5289)
SSSB = (-0.0024 , 0.5494 , 0.0637000000000001)

LSRE = Reference Elbow - Left Shoulder
LSRE = (Reference Elbow.X - Left Shoulder.X , Reference Elbow.Y - Left Shoulder.Y , Reference Elbow.Z - Left Shoulder.Z)
LSRE = (-0.1098 - -0.0419 , 0.6285 - 0.4528 , 1.5394 - 1.5394)
LSRE = (-0.0679 , 0.1757 , 0)

LELS = Left Shoulder - Left Elbow
LELS = (Left Shoulder.X - Left Elbow.X , Left Shoulder.Y - Left Elbow.Y , Left Shoulder.Z - Left Elbow.Z)
LELS = (-0.0419 - -0.1098 , 0.4528 - 0.6285 , 1.5734 - 1.5394)
LELS = (0.0679 , -0.1757 , 0.0339999999999998)

LELW = Left Wrist - Left Elbow
LELW = (Left Wrist.X - Left Elbow.X , Left Wrist.Y - Left Elbow.Y , Left Wrist.Z - Left Elbow.Z)
LELW = (-0.0927 - -0.1098 , 0.7992 - 0.6285 , 1.4942 - 1.5394)
LELW = (0.0171 , 0.1707 , -0.0452000000000001)

SBSS = Spine Shoulder - Spine Base
SBSS = (Spine Shoulder.X - Spine Base.X , Spine Shoulder.Y - Spine Base.Y , Spine Shoulder.Z - Spine Base.Z)
SBSS = (0.1116 - 0.1092 , -0.1217 - 0.4277 , 1.5289 - 1.5926)
SBSS = (-0.0024 , 0.5494 , 0.0637000000000001)

n-LELS-LELW = LELS x LELW
n-LELS-LELW = (LELS.Y * LELW.Z - LELS.Z * LELW.Y , LELS.Z * LELW.X - LELS.X * LELW.Z , LELS.X * LELW.Y - LELS.Y * LELW.X)
n-LELS-LELW = (-0.1757 * -0.0452000000000001 - 0.0339999999999998 * 0.1707 , 0.0339999999999998 * 0.0171 - 0.0679 * -0.0452000000000001 , 0.0679 * 0.1707 - -0.1757 * 0.0171)
n-LELS-LELW = (0.00213784000000005 , 0.00365048 , 0.014595)

n-LELS-SBSS = LELS x SBSS
n-LELS-SBSS = (LELS.Y * SBSS.Z - LELS.Z * SBSS.Y , LELS.Z * SBSS.X - LELS.X * SBSS.Z , LELS.X * SBSS.Y - LELS.Y * SBSS.X)
n-LELS-SBSS = (-0.1757 * 0.0637000000000001 - 0.0339999999999998 * 0.5494 , 0.0339999999999998 * -0.0024 - 0.0679 * 0.0637000000000001 , 0.0679 * 0.5494 - -0.1757 * -0.0024)
n-LELS-SBSS = (-0.0298716899999999 , -0.0044068300000001 , 0.03688258)

Flexion Angle = COS^-1((SSSB.X*LSRE.X+SSSB.Y*LSRE.Y+SSSB.Z*LSRE.Z)/((SQRT(SSSB.X*SSSB.X+SSSB.Y*SSSB.Y+SSSB.Z*SSSB.Z))*(SQRT(LSRE.X*LSRE.X+LSRE.Y*LSRE.Y+LSRE.Z*LSRE.Z))))
Flexion Angle = COS^-1((-0.0024 * -0.0679 + 0.5494 * 0.1757 + 0.0637000000000001 * 0) / (SQRT(-0.0024 * -0.0024 + 0.5494 * 0.5494 + 0.0637000000000001 * 0.0637000000000001) * SQRT(-0.0679 * -0.0679 + 0.1757 * 0.1757 + 0 * 0)))
Flexion Angle = 153.2399669
Flexion Angle Error = 0.3355331008

Abduction Angle Sign = if LE.Z<ER.Z,-1 | if LE.Z>=ER.Z,1
Abduction Angle Sign = -1
Abduction Angle = 90 + COS^-1((LSLE.X*LSRE.X+LSLE.Y*LSRE.Y+LSLE.Z*LSRE.Z)/((SQRT(LSLE.X*LSLE.X+LSLE.Y*LSLE.Y+LSLE.Z*LSLE.Z))*(SQRT(LSRE.X*LSRE.X+LSRE.Y*LSRE.Y+LSRE.Z*LSRE.Z))))
Abduction Angle = 90 + COS^-1((-0.0679 * -0.0679 + 0.1757 * 0.1757 + -0.0339999999999998 * 0) / (SQRT(-0.0679 * -0.0679 + 0.1757 * 0.1757 + -0.0339999999999998 * -0.0339999999999998) * SQRT(-0.0679 * -0.0679 + 0.1757 * 0.1757 + 0 * 0)))
Abduction Angle = 79.7681784675772
Abduction Angle Error = 0.02877846758

Rotation Angle = COS^-1((n-LELS-LELW.X*n-LELS-SBSS.X+n-LELS-LELW.Y*n-LELS-SBSS.Y+n-LELS-LELW.Z*n-LELS-SBSS.Z)/((SQRT(n-LELS-LELW.X*n-LELS-LELW.X+n-LELS-LELW.Y*n-LELS-LELW.Y+n-LELS-LELW.Z*n-LELS-LELW.Z))*(SQRT(n-LELS-SBSS.X*n-LELS-SBSS.X+n-LELS-SBSS.Y*n-LELS-SBSS.Y+n-LELS-SBSS.Z*n-LELS-SBSS.Z))))
Rotation Angle = COS^-1((0.00213784000000005 * -0.0298716899999999 + 0.00365048 * -0.0044068300000001 + 0.014595 * 0.03688258) / (SQRT(0.00213784000000005 * 0.00213784000000005 + 0.00365048 * 0.00365048 + 0.014595 * 0.014595) * SQRT(-0.0298716899999999 * -0.0298716899999999 + -0.0044068300000001 * -0.0044068300000001 + 0.03688258 * 0.03688258)))
Rotation Angle = 50.74277805
Rotation Angle Error = 0.5884219468
```

TRIAL 3
```text
LSLE = Left Elbow - Left Shoulder
LSLE = (Left Elbow.X - Left Shoulder.X , Left Elbow.Y - Left Shoulder.Y , Left Elbow.Z - Left Shoulder.Z)
LSLE = (-0.054 - -0.0257 , 0.3883 - 0.3529 , 1.2778 - 1.532)
LSLE = (-0.0283 , 0.0354 , -0.2542)

SSSB = Spine Base - Spine Shoulder
SSSB = (Spine Base.X - Spine Shoulder.X , Spine Base.Y - Spine Shoulder.Y , Spine Base.Z - Spine Shoulder.Z)
SSSB = (0.1124 - 0.1365 , 0.4171 - -0.1591 , 1.5849 - 1.5228)
SSSB = (-0.0241 , 0.5762 , 0.0621000000000001)

LSRE = Reference Elbow - Left Shoulder
LSRE = (Reference Elbow.X - Left Shoulder.X , Reference Elbow.Y - Left Shoulder.Y , Reference Elbow.Z - Left Shoulder.Z)
LSRE = (-0.054 - -0.0257 , 0.3883 - 0.3529 , 1.2778 - 1.2778)
LSRE = (-0.0283 , 0.0354 , 0)

LELS = Left Shoulder - Left Elbow
LELS = (Left Shoulder.X - Left Elbow.X , Left Shoulder.Y - Left Elbow.Y , Left Shoulder.Z - Left Elbow.Z)
LELS = (-0.0257 - -0.054 , 0.3529 - 0.3883 , 1.532 - 1.2778)
LELS = (0.0283 , -0.0354 , 0.2542)

LELW = Left Wrist - Left Elbow
LELW = (Left Wrist.X - Left Elbow.X , Left Wrist.Y - Left Elbow.Y , Left Wrist.Z - Left Elbow.Z)
LELW = (-0.0255 - -0.054 , 0.396 - 0.3883 , 1.0272 - 1.2778)
LELW = (0.0285 , 0.00770000000000004 , -0.2506)

SBSS = Spine Shoulder - Spine Base
SBSS = (Spine Shoulder.X - Spine Base.X , Spine Shoulder.Y - Spine Base.Y , Spine Shoulder.Z - Spine Base.Z)
SBSS = (0.1365 - 0.1124 , -0.1591 - 0.4171 , 1.5228 - 1.5849)
SBSS = (-0.0241 , 0.5762 , 0.0621000000000001)

n-LELS-LELW = LELS x LELW
n-LELS-LELW = (LELS.Y * LELW.Z - LELS.Z * LELW.Y , LELS.Z * LELW.X - LELS.X * LELW.Z , LELS.X * LELW.Y - LELS.Y * LELW.X)
n-LELS-LELW = (-0.0354 * -0.2506 - 0.2542 * 0.00770000000000004 , 0.2542 * 0.0285 - 0.0283 * -0.2506 , 0.0283 * 0.00770000000000004 - -0.0354 * 0.0285)
n-LELS-LELW = (0.00691389999999999 , 0.01433668 , 0.00122681)

n-LELS-SBSS = LELS x SBSS
n-LELS-SBSS = (LELS.Y * SBSS.Z - LELS.Z * SBSS.Y , LELS.Z * SBSS.X - LELS.X * SBSS.Z , LELS.X * SBSS.Y - LELS.Y * SBSS.X)
n-LELS-SBSS = (-0.0354 * 0.0621000000000001 - 0.2542 * 0.5762 , 0.2542 * -0.0241 - 0.0283 * 0.0621000000000001 , 0.0283 * 0.5762 - -0.0354 * -0.0241)
n-LELS-SBSS = (-0.14866838 , -0.00788365 , 0.01545332)

Flexion Angle = COS^-1((SSSB.X*LSRE.X+SSSB.Y*LSRE.Y+SSSB.Z*LSRE.Z)/((SQRT(SSSB.X*SSSB.X+SSSB.Y*SSSB.Y+SSSB.Z*SSSB.Z))*(SQRT(LSRE.X*LSRE.X+LSRE.Y*LSRE.Y+LSRE.Z*LSRE.Z))))
Flexion Angle = COS^-1((-0.0241 * -0.0283 + 0.5762 * 0.0354 + 0.0621000000000001 * 0) / (SQRT(-0.0241 * -0.0241 + 0.5762 * 0.5762 + 0.0621000000000001 * 0.0621000000000001) * SQRT(-0.0283 * -0.0283 + 0.0354 * 0.0354 + 0 * 0)))
Flexion Angle = 92.02555808
Flexion Angle Error = 0.01105807532

Abduction Angle Sign = if LE.Z<ER.Z,-1 | if LE.Z>=ER.Z,1
Abduction Angle Sign = -1
Abduction Angle = 90 + COS^-1((LSLE.X*LSRE.X+LSLE.Y*LSRE.Y+LSLE.Z*LSRE.Z)/((SQRT(LSLE.X*LSLE.X+LSLE.Y*LSLE.Y+LSLE.Z*LSLE.Z))*(SQRT(LSRE.X*LSRE.X+LSRE.Y*LSRE.Y+LSRE.Z*LSRE.Z))))
Abduction Angle = 90 + COS^-1((-0.0283 * -0.0283 + 0.0354 * 0.0354 + -0.2542 * 0) / (SQRT(-0.0283 * -0.0283 + 0.0354 * 0.0354 + -0.2542 * -0.2542) * SQRT(-0.0283 * -0.0283 + 0.0354 * 0.0354 + 0 * 0)))
Abduction Angle = 10.1091123211153
Abduction Angle Error = 0.002912321115

Rotation Angle = COS^-1((n-LELS-LELW.X*n-LELS-SBSS.X+n-LELS-LELW.Y*n-LELS-SBSS.Y+n-LELS-LELW.Z*n-LELS-SBSS.Z)/((SQRT(n-LELS-LELW.X*n-LELS-LELW.X+n-LELS-LELW.Y*n-LELS-LELW.Y+n-LELS-LELW.Z*n-LELS-LELW.Z))*(SQRT(n-LELS-SBSS.X*n-LELS-SBSS.X+n-LELS-SBSS.Y*n-LELS-SBSS.Y+n-LELS-SBSS.Z*n-LELS-SBSS.Z))))
Rotation Angle = COS^-1((0.00691389999999999 * -0.14866838 + 0.01433668 * -0.00788365 + 0.00122681 * 0.01545332) / (SQRT(0.00691389999999999 * 0.00691389999999999 + 0.01433668 * 0.01433668 + 0.00122681 * 0.00122681) * SQRT(-0.14866838 * -0.14866838 + -0.00788365 * -0.00788365 + 0.01545332 * 0.01545332)))
Rotation Angle = 118.0046869
Rotation Angle Error = 0.04888693266
```

TRIAL2
```text
LSLE = Left Elbow - Left Shoulder
LSLE = (Left Elbow.X - Left Shoulder.X , Left Elbow.Y - Left Shoulder.Y , Left Elbow.Z - Left Shoulder.Z)
LSLE = (-0.054 - -0.0257 , 0.3883 - 0.3529 , 1.2778 - 1.532)
LSLE = (-0.0283 , 0.0354 , -0.2542)

SSSB = Spine Base - Spine Shoulder
SSSB = (Spine Base.X - Spine Shoulder.X , Spine Base.Y - Spine Shoulder.Y , Spine Base.Z - Spine Shoulder.Z)
SSSB = (0.1124 - 0.1365 , 0.4171 - -0.1591 , 1.5849 - 1.5228)
SSSB = (-0.0241 , 0.5762 , 0.0621000000000001)

LSRE = Reference Elbow - Left Shoulder
LSRE = (Reference Elbow.X - Left Shoulder.X , Reference Elbow.Y - Left Shoulder.Y , Reference Elbow.Z - Left Shoulder.Z)
LSRE = (-0.054 - -0.0257 , 0.3883 - 0.3529 , 1.2778 - 1.2778)
LSRE = (-0.0283 , 0.0354 , 0)

LELS = Left Shoulder - Left Elbow
LELS = (Left Shoulder.X - Left Elbow.X , Left Shoulder.Y - Left Elbow.Y , Left Shoulder.Z - Left Elbow.Z)
LELS = (-0.0257 - -0.054 , 0.3529 - 0.3883 , 1.532 - 1.2778)
LELS = (0.0283 , -0.0354 , 0.2542)

LELW = Left Wrist - Left Elbow
LELW = (Left Wrist.X - Left Elbow.X , Left Wrist.Y - Left Elbow.Y , Left Wrist.Z - Left Elbow.Z)
LELW = (-0.0255 - -0.054 , 0.396 - 0.3883 , 1.0272 - 1.2778)
LELW = (0.0285 , 0.00770000000000004 , -0.2506)

SBSS = Spine Shoulder - Spine Base
SBSS = (Spine Shoulder.X - Spine Base.X , Spine Shoulder.Y - Spine Base.Y , Spine Shoulder.Z - Spine Base.Z)
SBSS = (0.1365 - 0.1124 , -0.1591 - 0.4171 , 1.5228 - 1.5849)
SBSS = (-0.0241 , 0.5762 , 0.0621000000000001)

n-LELS-LELW = LELS x LELW
n-LELS-LELW = (LELS.Y * LELW.Z - LELS.Z * LELW.Y , LELS.Z * LELW.X - LELS.X * LELW.Z , LELS.X * LELW.Y - LELS.Y * LELW.X)
n-LELS-LELW = (-0.0354 * -0.2506 - 0.2542 * 0.00770000000000004 , 0.2542 * 0.0285 - 0.0283 * -0.2506 , 0.0283 * 0.00770000000000004 - -0.0354 * 0.0285)
n-LELS-LELW = (0.00691389999999999 , 0.01433668 , 0.00122681)

n-LELS-SBSS = LELS x SBSS
n-LELS-SBSS = (LELS.Y * SBSS.Z - LELS.Z * SBSS.Y , LELS.Z * SBSS.X - LELS.X * SBSS.Z , LELS.X * SBSS.Y - LELS.Y * SBSS.X)
n-LELS-SBSS = (-0.0354 * 0.0621000000000001 - 0.2542 * 0.5762 , 0.2542 * -0.0241 - 0.0283 * 0.0621000000000001 , 0.0283 * 0.5762 - -0.0354 * -0.0241)
n-LELS-SBSS = (-0.14866838 , -0.00788365 , 0.01545332)

Flexion Angle = COS^-1((SSSB.X*LSRE.X+SSSB.Y*LSRE.Y+SSSB.Z*LSRE.Z)/((SQRT(SSSB.X*SSSB.X+SSSB.Y*SSSB.Y+SSSB.Z*SSSB.Z))*(SQRT(LSRE.X*LSRE.X+LSRE.Y*LSRE.Y+LSRE.Z*LSRE.Z))))
Flexion Angle = COS^-1((-0.0241 * -0.0283 + 0.5762 * 0.0354 + 0.0621000000000001 * 0) / (SQRT(-0.0241 * -0.0241 + 0.5762 * 0.5762 + 0.0621000000000001 * 0.0621000000000001) * SQRT(-0.0283 * -0.0283 + 0.0354 * 0.0354 + 0 * 0)))
Flexion Angle = 92.02555808
Flexion Angle Error = 0.01105807532

Abduction Angle Sign = if LE.Z<ER.Z,-1 | if LE.Z>=ER.Z,1
Abduction Angle Sign = -1
Abduction Angle = 90 + COS^-1((LSLE.X*LSRE.X+LSLE.Y*LSRE.Y+LSLE.Z*LSRE.Z)/((SQRT(LSLE.X*LSLE.X+LSLE.Y*LSLE.Y+LSLE.Z*LSLE.Z))*(SQRT(LSRE.X*LSRE.X+LSRE.Y*LSRE.Y+LSRE.Z*LSRE.Z))))
Abduction Angle = 90 + COS^-1((-0.0283 * -0.0283 + 0.0354 * 0.0354 + -0.2542 * 0) / (SQRT(-0.0283 * -0.0283 + 0.0354 * 0.0354 + -0.2542 * -0.2542) * SQRT(-0.0283 * -0.0283 + 0.0354 * 0.0354 + 0 * 0)))
Abduction Angle = 10.1091123211153
Abduction Angle Error = 0.002912321115

Rotation Angle = COS^-1((n-LELS-LELW.X*n-LELS-SBSS.X+n-LELS-LELW.Y*n-LELS-SBSS.Y+n-LELS-LELW.Z*n-LELS-SBSS.Z)/((SQRT(n-LELS-LELW.X*n-LELS-LELW.X+n-LELS-LELW.Y*n-LELS-LELW.Y+n-LELS-LELW.Z*n-LELS-LELW.Z))*(SQRT(n-LELS-SBSS.X*n-LELS-SBSS.X+n-LELS-SBSS.Y*n-LELS-SBSS.Y+n-LELS-SBSS.Z*n-LELS-SBSS.Z))))
Rotation Angle = COS^-1((0.00691389999999999 * -0.14866838 + 0.01433668 * -0.00788365 + 0.00122681 * 0.01545332) / (SQRT(0.00691389999999999 * 0.00691389999999999 + 0.01433668 * 0.01433668 + 0.00122681 * 0.00122681) * SQRT(-0.14866838 * -0.14866838 + -0.00788365 * -0.00788365 + 0.01545332 * 0.01545332)))
Rotation Angle = 118.0046869
Rotation Angle Error = 0.04888693266
```
