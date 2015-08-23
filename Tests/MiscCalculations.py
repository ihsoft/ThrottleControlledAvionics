'''
Created on Jan 8, 2015

@author: Allis Tauri
'''

import numpy as np
import matplotlib.pyplot as plt
import pandas as pa
import sys
import os


def clampL(x, L): return x if x > L else L
def clampH(x, H): return x if x < H else H

def clamp(x, L, H): 
    if x > H: return H
    elif x < L: return L
    return x
#end def

def clamp01(x): 
    if x > 1: return 1.0
    elif x < 0: return 0.0
    return x
#end def

def asymp01(x, k=1):
    return 1.0-1.0/(x/k+1.0); 

vclamp01 = np.vectorize(clamp01)

class vec(object):
    def __init__(self, x=0, y=0, z=0):
        self.v = np.array([float(x), float(y), float(z)])

    @property
    def norm(self): 
        return vec.from_array(np.array(self.v)/np.linalg.norm(self.v))
    
    def __str__(self):
        return '[%+.4f, %+.4f, %+.4f] |%.4f|' % tuple(list(self.v)+[abs(self),])
    
    def __repr__(self): return str(self)
    
    def __getitem__(self, index): return self.v[index]
    def __setitem__(self, index, value): self.v[index] = value
    
    def __abs__(self):
        return np.linalg.norm(self.v)
    
    def __add__(self, other):
        return vec.from_array(self.v+other.v)
    
    def __iadd__(self, other):
        self[0] += other[0]
        self[1] += other[1]
        self[2] += other[2]
        return self
    
    def __sub__(self, other):
        return vec.from_array(self.v-other.v)
    
    def __neg__(self):
        return self * -1
    
    def __rmul__(self, other): return self * other
    
    def __mul__(self, other):
        if isinstance(other, vec):
            return np.dot(self.v, other.v)
        elif isinstance(other, (int, float)):
            return vec.from_array(self.v * float(other))
        raise TypeError('vec: unsupported multiplier type %s' % type(other))
    
    def __div__(self, other):
        return self * (1.0/other)
    
    def cross(self, other):
        return vec.from_array(np.cross(self.v, other.v))

    def project(self, onto):
        m2 = onto*onto
        return onto * (self*onto/m2)
    
    def angle(self, other):
        return np.rad2deg(np.arccos(self*other/(abs(self)*abs(other))))
    
    def cube_norm(self):
        return self/max(abs(x) for x in self)
    
    @classmethod
    def from_array(cls, a):
        assert len(a) == 3, 'Array should be 1D with 3 elements'
        return vec(a[0], a[1], a[2])
    
    @classmethod
    def sum(cls, vecs): return sum(vecs, vec())
#end class

class vec6(object):
    def __init__(self):
        self.positive = vec()
        self.negative = vec()
        
    def add(self, v):
        for i, d in enumerate(v):
            if d >= 0: self.positive[i] += d
            else: self.negative[i] += d
            
    def sum(self, vecs):
        for v in vecs: self.add(v)
        
    def clamp(self, v):
        c = vec()
        for i, d in enumerate(v):
            if d >= 0: c[i] = min(d, self.positive[i])
            else: c[i] = max(d, self.negative[i])
        return c
          
    def __str__(self):
        return 'positive: %s\nnegative: %s' % (self.positive, self.negative)
    
    def __repr__(self): return str(self)
#end class

def lerp(f, t, time): return f+(t-f)*clamp01(time)

class engine(object):
    def __init__(self, pos, direction, spec_torque, min_thrust=0.0, max_thrust=100.0, maneuver=False, manual=False):
        self.pos = pos
        self.dir = direction
        self.torque = spec_torque
        self.min_thrust = float(min_thrust)
        self.max_thrust = float(max_thrust) 
        self.limit  = 1.0
        self.limit_tmp = 1.0
        self.best_limit = 1.0
        self.torque_ratio = 1.0
        self.current_torque = vec()
        self.maneuver = maneuver
        self.manual = manual
        
    def nominal_current_torque(self, K):
            return (self.torque *
                    (lerp(self.min_thrust, self.max_thrust, K) if not self.manual
                     else self.max_thrust))
            
    def vsf(self, K): return (1 if self.maneuver else K)
#end class

class PID(object):
    def __init__(self, kp, ki, kd, min_a, max_a):
        self.kp = float(kp)
        self.ki = float(ki)
        self.kd = float(kd)
        self.min = float(min_a)
        self.max = float(max_a)
        
        self.value  = 0
        self.ierror = 0
        self.perror = 0
        self.action = 0
    #end def
        
    def update(self, err):
        if self.perror == 0: self.perror = err
        old_ierror = self.ierror
        self.ierror += err*dt
#         self.ierror  = clamp(self.ierror, self.min, self.max)
        act = self.kp*err + self.ki*self.ierror + self.kd*(err-self.perror)/dt
        clamped = clamp(act, self.min, self.max)
        if clamped != act: self.ierror = old_ierror
        self.perror = err
        self.action = clamped
        
        return self.action
    #end def
    
    def sim(self, PV, SV, T):
        V = [0.0]
        for sv in SV[1:]:
            act = self.update(sv-V[-1])
            if np.isinf(act) or np.isnan(act): 
                act = sys.float_info.max
            V.append(V[-1]+act)
        #plot
        V = np.array(V); SV = np.array(SV)
        plt.subplot(3,1,1)
        plt.plot(T, SV)
        plt.subplot(3,1,2)
        plt.plot(T, V)
        plt.subplot(3,1,3)
        plt.plot(T, V-SV)
        
    def __str__(self, *args, **kwargs):
        return ('p % 8.5f, i % 8.5f, d % 8.5f, min % 8.5f, max % 8.5f; action = % 8.5f'
                % (self.kp, self.ki, self.kd, self.min, self.max, self.action))
#end class

class PID2(PID):
    def update(self, err):
        if self.perror == 0: self.perror = err
        d = self.kd * (err-self.perror)/dt
        self.ierror = clamp(self.ierror + self.ki * err * dt if abs(d) < 0.6*self.max else 0.9 * self.ierror, self.min, self.max)
        self.perror = err
        self.action = clamp(self.kp*err + self.ierror + d, self.min, self.max)
#         print '%f %+f %+f' % (self.kp*err, self.ierror, d)
        return self.action

class VSF_sim(object):
    t1 = 5.0
    
    def __init__(self,  ter=None, AS=0, DS=0):
        self.Ter = list(ter) if ter is not None else None
        self.N   = 0 if self.Ter is None else len(self.Ter)
        self.AS  = AS
        self.DS  = DS
        
        self.maxV = 0.0
        self.VSP  = 0.0
        self.upA  = 0.0
        self.upV  = 0.0
        self.rV   = 0.0
        self.upX  = 0.0
        self.dX   = 0.0
        self.E    = 0.0
        self.upAF = 0.0
        
        self.T   = []
        self.X   = []
        self.rX  = []
        self.V   = []
        self.rV  = []
        self.K   = []
        self.F   = []
        self.VSp = []
        
        self.M = 4.0
        self.MinVSF = 0.1
        
        self.vK1_pid = PID(0.3, 0.1, 0.3, 0.0, 1.0)
    #end def
        
    def vK1(self):
#         upAF = 0.0
#         if self.upA < 0 and self.AS > 0: upAF = (1.0/self.AS)*2
#         elif self.DS > 0: upAF = (1.0/self.DS)*1
#         upAF *= -self.upA*0.04
#         self.VSP = self.maxV+(2.0+upAF)/self.twr
#         self.E = self.VSP-self.upV
        return self.vK1_pid.update(self.E)

        
    def vK2(self):
#         print('Thrust %.2f, W %.2f, H %.2f, upV %.2f, E %.2f, upA %.2f, upAF %.3f, dVSP %.2f, K0 %.3f, K1 %.3f' 
#               % (self.cthrust, self.M*9.81, self.upX, self.upV, self.maxV-self.upV, self.upA, upAF, (2.0+upAF)/self.twr, 
#                  clamp01(self.E/2.0/(clampL(self.upA/self.K1+1.0, self.L1)**2)),
#                  clamp01(self.E/2.0/(clampL(self.upA/self.K1+1.0, self.L1)**2)+upAF)))
        #return clampL(clamp01(self.E/2.0/(clampL(self.upA/self.K1+1.0, self.L1)**2)+upAF), 0.05)
#         if self.upV <= self.maxV:
        K = clamp01(self.E*0.5+self.upAF)
#         else: 
#             K = clamp01(self.E*self.upA*0.5+self.upAF)
        return clampL(K, self.MinVSF)
    
    _vK = vK2
        
    @property
    def vK(self):
        self.E = self.VSP-self.upV 
        return self._vK()

    def init(self, thrust):
        self.thrust = thrust
        self.add_thrust = 0
        self.twr = thrust/9.81/self.M
        self.upA = 0.0
        self.dV  = self.upV
        self.dX = self.upX-self.Ter[0] if self.N > 0 else 0
        self.T  = [0.0]
        self.A  = [self.upA]
        self.V  = [self.upV]
        self.rV = [self.dV]
        self.X  = [self.upX]
        self.rX = [self.dX]
        self.K  = [self.vK]
        self.F  = [0.0]
    #end def
    
    def update_upAF(self):
        self.upAF = 0.0
        if self.upA < 0 and self.AS > 0: self.upAF = (1.0/self.AS)*2
        elif self.DS > 0: self.upAF = (1.0/self.DS)*1
        self.upAF = -self.upA*0.2*self.upAF
        self.VSP = self.maxV+(2.0+self.upAF)/self.twr
    #end def
    
    def phys_loop(self, on_frame=lambda: None):
        i = 1
        while self.dX >= 0 and (self.T[-1] < self.t1 or i < self.N): 
            self.T.append(self.T[-1]+dt)
            self.update_upAF()
            on_frame()
            #VSF
            self.K.append(self.vK)
            #thrust
            rthrust = self.thrust*self.K[-1]
            speed   = self.AS if rthrust > self.cthrust else self.DS
            self.cthrust = lerp(self.cthrust, rthrust, speed*dt) if speed > 0 else rthrust
            #dynamics
            self.upA  = (self.add_thrust + self.cthrust - self.M*9.81)/self.M
            self.upV += self.upA*dt
            self.upX += self.upV*dt
            self.dX   = self.upX - (self.Ter[i] if self.N > 0 else 0)
            self.dV   = EWA(self.dV, (self.dX-self.rX[-1])/dt, 0.1) 
            #logging
            self.F.append(self.cthrust * dt)
            self.A.append(self.upA)
            self.V.append(self.upV)
            self.rV.append(self.dV)
            self.X.append(self.upX)
            self.rX.append(self.dX)
            i += 1
    #end def
    
    def run(self, upV, maxV=1.0, thrust=20.0, vK = None):
        if vK is not None: self._vK = vK
        self.cthrust = self.M*9.81
        self.maxV = maxV
        self.VSP  = maxV
        self.upV  = upV
        self.upX  = 100.0
        self.init(thrust)
        self.phys_loop()
    #end def
    
    def run_impulse(self, dthrust = 10, impulse=0.1, maxV=1.0, thrust=20.0):
        self._vK = self.vK2
        self.cthrust = self.M*9.81
        self.maxV = maxV
        self.VSP  = maxV
        self.upV  = maxV
        self.upX  = 100.0
        self.init(thrust)
        def on_frame(): 
            if 3 < self.T[-1] < 3+impulse:
                self.add_thrust = dthrust
            else: self.add_thrust = 0
            self.twr = (self.thrust+self.add_thrust)/9.81/self.M
        self.phys_loop(on_frame)
    #end def
            
    def run_alt(self, alt, salt = 0.0, thrust=20.0, pid = PID(0.5, 0.0, 0.5, -9.9, 9.9)):
        self.pid = pid
        self._vK = self.vK2
        self.cthrust = self.M*9.81
        self.maxV = 0.0
        self.VSP  = 0.0
        self.upV  = 0.0
        self.upX  = salt if self.Ter is None else self.Ter[0]+10
        self.Vsp  = [self.maxV]
        self.dVsp = [0] 
        self.init(thrust)
        d = pid.kd
        def on_frame():
            alt_err = alt-self.dX
            if (self.AS > 0 or self.DS > 0):
                if alt_err > 0:
                    self.pid.kp = clamp(0.01*abs(alt_err)/clampL(self.upV, 1), 0.0, d)
                elif alt_err < 0:
                    self.pid.kp = clamp(self.twr**2/clampL(-self.upV, 1), 0.0, clampH(d*self.twr/2, d))
                else: self.pid.kp = d
            self.pid.kd = d/clampL(self.dX, 1)
            if alt_err < 0: alt_err = alt_err/clampL(self.dX, 1)
            self.maxV = self.pid.update(alt_err)
            print self.pid, alt_err, clamp(0.01*abs(alt_err)/clampL(self.upV, 1), 0.0, d), d 
            if self.N > 0:
                dV = (self.upV-self.dV)/clampL(self.dX, 1)
                if alt_err < 0: 
#                     print '% f %+f = %f' % (dV/clampL(self.dX/50, 1), clampL(alt_err*self.dX/5000*self.twr, self.pid.min*10), dV/clampL(self.dX/50, 1) + clampL(alt_err*self.dX/5000*self.twr, self.pid.min*10))
                    dV = dV + clampL(alt_err*self.dX/500*self.twr, self.pid.min*10)
                else: 
                    dV = clampL(dV, 0)
#                 print dV
                self.dVsp.append(dV)
                self.maxV += dV
            self.Vsp.append(self.maxV)
        self.phys_loop(on_frame)
    #end def
        
#         print(("Start velocity: %f\n"
#                "K1 %f; L1 %f; K2 %f L2 %f\n"
#                "Fuel consumed: %f\n") 
#               % (upV, self.K1, self.L1, self.K2, self.L2, sum(self.F)))
    #end def
    
    def describe(self):
        from scipy import stats
        cols = ('X', 'rX', 'V', 'rV', 'Vsp', 'dVsp', 'K')
        for n in cols: 
            c = getattr(self, n)
            d = stats.describe(c)
            print '%s:' % n
            print '   sum:    ', sum(c)
            print '   min-max:', d.minmax
            print '   mean:   ', d.mean
            print '   median: ', np.median(c)
            print '   std:    ', np.std(c)
            print '   sem:    ', stats.sem(c)
            print '   skew:   ', d.skewness
            print '   hist:   '
            h = np.histogram(c, normed=True)
            for i, e in enumerate(h[1][1:]):
                e0 = h[1][i]
                print '[% 8.3f : % 8.3f]: %s' %(e0, e, "#"*int(h[0][i]*80))
            print ''
        print '\n'
    
    def _plot(self, r, c, n, Y, ylab):
        plt.subplot(r, c, n)
        plt.plot(self.T, Y, label=("V: twr=%.1f" % self.twr))
        plt.ylabel(ylab)
        
    def legend(self):
        plt.legend(bbox_to_anchor=(1.05, 1), loc=2, borderaxespad=0.)
    
    def plot_a(self, r, c, n):
        self._plot(r, c, n, self.A, ylab="vertical acceleration (m/s2)")
    
    def plot_vs(self, r, c, n):
        self._plot(r, c, n, self.V, ylab="vertical speed (m/s)")
        
    def plot_ter(self, r, c, n):
        if self.N == 0: return
        self._plot(r, c, n, self.Ter[:len(self.T)], ylab="terrain (m)")
        
    def plot_alt(self, r, c, n):
        self._plot(r, c, n, self.X, ylab="altitude (m)")
        
    def plot_ralt(self, r, c, n):
        self._plot(r, c, n, self.rX, ylab="relative altitude (m)")
        
    def plot_vsp(self, r, c, n):
        self._plot(r, c, n, self.Vsp, ylab="VSP (m/s)")
        
    def plot_dvsp(self, r, c, n):
        if len(self.dVsp) != len(self.T): return
        self._plot(r, c, n, self.dVsp, ylab="dVSP (m/s)")
        
    def plot_k(self, r, c, n):
        self._plot(r, c, n, self.K, ylab="K")
#end class

def sim_PID():
    np.random.seed(42)
    
    def rSV(val, delta): 
        return max(0, min(100, 
                          val + (delta * np.random.random()-delta/2.0)))

    t1  = 10.0
    PV  = 10.0
    SV  = [rSV(50, 100)]
    T   = np.arange(0, t1, PID.dt)
    sSV = SV[-1]
    for _t in T[1:]:
        r = np.random.random()
        if r < 0.98:
            SV.append(SV[-1])
            continue
        sSV = rSV(sSV, 50)
        SV.append(sSV)
    
    pid1 = PID(0.8, 0.2, 0.001, -10, 10)
    pid2 = PID2(0.8, 0.2, 0.001, -10, 10)
    
    pid1.sim(PV, SV, T)
    pid2.sim(PV, SV, T)
    plt.show()
    

def sim_PIDf():
    MoI = vec(3.517439, 5.191057, 3.517369)
    def A(_t):  return vec(_t/MoI[0], _t/MoI[1], _t/MoI[2])
    def Tf(_t): return vec(MoI[0]/_t, MoI[1]/_t, MoI[2]/_t)
    ph = 0.4; pl = 0.05; dp = ph-pl 
    
    def hill(x, x0=1.0, k=1.0):
        p1 = x**2
        p2 = -(x*2-x0*3)
        p3 = (x*2+x0*3)
        return p1*p2*p3
    
    T = np.arange(0, 2, 0.01)
    P = []; I = []; 
    As = []; S = []; S1 = []; S2 = [];
    for t in T:
        As.append(abs(A(t)))
#         f = asymp01(As[-1], 10)
#         P.append(pl+dp*(1.0-f))
#         I.append(P[-1]*(1.0-f)/1.5)
        S.append(hill(t, 1, 1))
        
#     plt.plot(T, P)
#     plt.plot(T, I)
#     plt.show()
    plt.plot(T, S)
    plt.show()


# def tI_PCA():
#     from matplotlib.mlab import PCA
#     ships = 
#     [
#      
#      ]

# Quadro_Manual = [
#                     engine(vec(-0.8, 0.0, 0.0),  min_thrust=0.0, max_thrust=18.0, manual=True),
#                     engine(vec(1.8, 0.0, 1.8),   min_thrust=0.0, max_thrust=40.0),# maneuver=True),
#                     engine(vec(1.8, 0.0, -1.8),  min_thrust=0.0, max_thrust=40.0),# maneuver=True),
#                     engine(vec(-1.8, 0.0, -1.8), min_thrust=0.0, max_thrust=40.0),# maneuver=True),
#                     engine(vec(-1.8, 0.0, 1.8),  min_thrust=0.0, max_thrust=40.0),# maneuver=True),
#                  ]
#     
# VTOL_Test = [
#                 engine(vec(-3.4, -2.0, 0.0), min_thrust=0.0, max_thrust=250.0),
#                 engine(vec(-3.4, 2.0, 0.0),  min_thrust=0.0, max_thrust=250.0),
#                 engine(vec(3.5, -2.0, 0.0),  min_thrust=0.0, max_thrust=250.0),
#                 engine(vec(1.5, 2.0, 0.0),   min_thrust=0.0, max_thrust=250.0),
#                 engine(vec(1.3, 2.0, 1.6),   min_thrust=0.0, max_thrust=20.0, maneuver=True),
#                 engine(vec(3.1, -2.0, -3.7), min_thrust=0.0, max_thrust=20.0, maneuver=True),
#                 engine(vec(-3.1, -2.0, 3.7), min_thrust=0.0, max_thrust=20.0, maneuver=True),
#                 engine(vec(-2.4, 2.0, -2.9), min_thrust=0.0, max_thrust=20.0, maneuver=True),
#              ]
# 
# Hover_Test = [
#                 engine(vec(-6.2, 6.4, 0.6),   max_thrust=450),
#                 engine(vec(-6.2, -6.4, -0.6), max_thrust=450),
#                 engine(vec(3.9, 7.4, 0.6),    max_thrust=450),
#                 engine(vec(3.9, -6.4, -0.6),  max_thrust=450)
#             ]

Uneven_Test = [
               engine(vec(-0.1, -2.1, 0.0), vec(0.0, -1.0, 0.0), vec(0.0, 0.0, 0.1), 0, 200),
               engine(vec(-1.4, -1.4, 0.0), vec(0.0, -1.0, 0.0), vec(0.0, 0.0, 1.4), 0, 60),
               engine(vec(1.1, -1.4, 0.0), vec(0.0, -1.0, 0.0), vec(0.0, 0.0, -1.1), 0, 200),
               engine(vec(-0.1, 0.2, 0.8), vec(0.0, -1.0, 0.1), vec(0.8, 0.0, 0.1), 0, 16),
               engine(vec(-0.1, 0.2, -0.8), vec(0.0, -1.0, -0.1), vec(-0.8, 0.0, 0.1), 0, 16)
               ]

Shuttle_Test = [
                engine(vec(0.0, -5.9, -2.7), vec(0.0, -1.0, 0.0), vec(-2.7, 0.0, 0.0), 0, 1500),
                engine(vec(0.0, -6.2, 1.2), vec(0.0, -1.0, 0.0), vec(1.2, 0.0, 0.0), 0, 4000),
                ]

VTOL_Test_Bad_Demand = [
                        vec(0.0, 0.0, 0.0),
                        vec(10.0, 0.0, 0.0),
                        vec(0.0, 10.0, 0.0),
                        vec(0.0, 0.0, 10.0),
                            
                        vec(-1797.147, 112.3649, 80.1167), #Torque Error: 165.3752
                        vec(1327.126, -59.91731, 149.1847), #Torque Error: 229.8387
                        vec(107.5895, -529.4326, -131.0672), #Torque Error: 59.95838
                        vec(50.84914, -1.706408, 113.4622), #Torque Error: 25.10385
                        vec(-0.4953138, 0.2008617, 39.52808),
                        vec(14.88248, 0.9660782, -51.20171),
                        vec(-20.34281, -10.67025, 38.88113),
                        ]

Hover_Test_Bad_Demand = [
                         vec(0.2597602, -5.2778279, 0.8444),
                         vec(0.9042788, -1.347212, 483.4898), #Torque Error: 483.4926kNm, 90deg
                         vec(-0.7012861, 0.2607862, -294.2217), #Torque Error: 339.2753kNm, 95.00191deg
                         vec(0.2597602, -0.2778279, 295.8444), #Torque Error: 341.1038kNm, 94.96284deg
                         ]
    
def sim_Attitude():
    def S(T, K, L=0): return vec.sum(Tk(T, K, L))
    def Sm(T, K, L=0): return abs(S(T,K))
    def Tk(T, K, L=0): return [t*clampL(k, L) for t, k in zip(T,K)]
    
    def opt(target, engines, vK, eps):
        tm = abs(target)
        comp = vec()
        man  = vec()
        for e in engines:
            if not e.manual: 
                e.limit_tmp = -e.current_torque*target/tm/abs(e.current_torque)*e.torque_ratio
                if e.limit_tmp > 0:
                    comp += e.nominal_current_torque(e.vsf(vK)*e.limit)
                elif e.maneuver:
                    if e.limit == 0: e.limit = eps
                    man += e.nominal_current_torque(e.vsf(vK)*e.limit)
                else: e.limit_tmp = 0
            else: e.limit_tmp = 0
        compm = abs(comp)
        manm = abs(man)
        if compm < eps and manm == 0: return False
        limits_norm = clamp01(tm/compm)
        man_norm = clamp01(tm/manm)
        for e in engines:
            if e.manual: continue
            if e.limit_tmp < 0:
                e.limit = clamp01(e.limit * (1.0 - e.limit_tmp*man_norm))
            else:
                e.limit = clamp01(e.limit * (1.0 - e.limit_tmp*limits_norm))
        return True
    
    def optR(engines, D=vec(), vK=1.0, eps=0.1, maxI=500, output=True):
        torque_clamp = vec6()
        torque_imbalance = vec()
        ti_min = vec()
        for e in engines:
            e.limit = 1.0 if not e.maneuver else 0
            ti_min += e.nominal_current_torque(0)
        if abs(ti_min) > 0:
            print ti_min
            anti_ti_min = vec()
            for e in engines:
                if e.torque*ti_min < 0:
                    anti_ti_min += e.nominal_current_torque(1)
            if abs(anti_ti_min) > 0:
                vK = clampL(vK, clamp01(abs(ti_min)/abs(anti_ti_min)*1.2))
        for e in engines:
            e.torque_ratio = clamp01(1.0-abs(e.pos.norm*e.dir.norm))**0.1
            e.current_torque = e.nominal_current_torque(e.vsf(vK))
            torque_imbalance += e.nominal_current_torque(e.vsf(vK) * e.limit)
            torque_clamp.add(e.current_torque)
        _d = torque_clamp.clamp(D)
        if output:
            print 'vK: %f' % vK
            print 'Torque clamp:\n', torque_clamp
            print 'demand:        ', D
            print 'clamped demand:', _d
            print ('initial     %s, error %s, dir error %s' % 
                   (torque_imbalance, abs(torque_imbalance-_d), torque_imbalance.angle(_d)))
        s = []; s1 = []; i = 0;
        best_error = -1; best_angle = -1; best_index = -1;
        for i in xrange(maxI):
            s.append(abs(torque_imbalance-_d))
            s1.append(torque_imbalance.angle(_d) if abs(_d) > 0 else 0)
            if(s1[-1] <= 0 and s[-1] < best_error or 
               s[-1]+s1[-1] < best_error+best_angle or best_angle < 0):
                for e in engines: e.best_limit = e.limit
                best_error = s[-1]
                best_angle = s1[-1]
                best_index = len(s)-1
#             if len(s1) > 1 and s1[-1] < 55 and s1[-1]-s1[-2] > eps: break
#             if s1[-1] > 0:
#                 if s1[-1] < eps or len(s1) > 1 and abs(s1[-1]-s1[-2]) < eps*eps: break
#             elif 
            if s[-1] < eps or len(s) > 1 and abs(s[-1]-s[-2]) < eps/10.0: break
            if len(filter(lambda e: e.manual, engines)) == 0:
                mlim = max(e.limit for e in engines)
                if mlim > 0: 
                    for e in engines: e.limit = clamp01(e.limit/mlim)
            if not opt(_d-torque_imbalance, engines, vK, eps): break
            torque_imbalance = vec.sum(e.nominal_current_torque(e.vsf(vK) * e.limit) for e in engines)
        for e in engines: e.limit = e.best_limit
        if output:
            ##########
            print 'iterations:', i+1
#             print 'dAngle:    ', abs(s1[-1]-s1[-2])
            print 'limits:    ', list(e.limit for e in engines)
            print 'result      %s, error %s, dir error %s' % (torque_imbalance, s[best_index], s1[best_index])
            print 'engines:\n'+'\n'.join(str(e.nominal_current_torque(e.vsf(vK) * e.limit)) for e in engines)
            print
            ##########
            x = np.arange(len(s))
            plt.subplot(2,1,1)
            plt.plot(x, s, '-')
            plt.xlabel('iterations')
            plt.ylabel('torque error (kNm)')
            plt.subplot(2,1,2)
            plt.plot(x, s1, '-')
            plt.xlabel('iterations')
            plt.ylabel('torque direction error (deg)')
            ##########
        return s[best_index], s1[best_index]
    
    def test_craft(craft, demands, vK=1, eps=0.1, maxI=50):
        total_error = 0
        for d in demands: 
            total_error += sum(optR(craft, d, vK, eps, maxI))
        print 'total error:', total_error
        print '='*80+'\n\n'
        plt.show()
        
#     test_craft(VTOL_Test, VTOL_Test_Bad_Demand, vK=0.1, eps=0.01, maxI=50)
#     test_craft(Hover_Test, Hover_Test_Bad_Demand+VTOL_Test_Bad_Demand, vK=0.3, eps=0.1, maxI=50)
    
    test_craft(Shuttle_Test, VTOL_Test_Bad_Demand, vK=0.8, eps=0.01, maxI=50)
    
#     N = range(500)
#     np.random.seed(42)
#     random_tests = [vec(200*np.random.random()-100.0,
#                         200*np.random.random()-100.0,
#                         200*np.random.random()-100.0) 
#                     for _n in N]
#     E = []; A = []; X = []; Y = []; Z = [];
#     for d in random_tests:
#         e, a = optR(Hover_Test, d, vK=0.5, eps=0.1, maxI=30, output=False)
#         dm = abs(d)
#         E.append(e/dm*100); A.append(a);
#         X.append(d[0]/dm*100); Y.append(d[1]/dm*100); Z.append(d[2]/dm*100)
#          
#     plt.subplot(4,1,1)
#     plt.plot(A, E, 'o')
#     plt.xlabel('angle')
#     plt.ylabel('torque error (%)')
#     plt.subplot(4,1,2)
#     plt.plot(X, A, 'o')
#     plt.xlabel('x %')
#     plt.ylabel('angle')
#     plt.subplot(4,1,3)
#     plt.plot(Y, A, 'o')
#     plt.xlabel('y %')
#     plt.ylabel('angle')
#     plt.subplot(4,1,4)
#     plt.plot(Z, A, 'o')
#     plt.xlabel('z %')
#     plt.ylabel('angle')
#     plt.show()


def linalg_Attitude():
    def engines2a(engines):
        num_e = len(engines)
        a = np.array([[None]*num_e, [None]*num_e, [None]*num_e], dtype=float)
        for i, e in enumerate(engines):
            t = e.nominal_current_torque(1)
            a[0,i] = t[0]
            a[1,i] = t[1]
            a[2,i] = t[2]
        return a
    
    for d in VTOL_Test_Bad_Demand: 
        a = engines2a(Uneven_Test)
        x, r, R, s = np.linalg.lstsq(a, d.v)
        print "demand: %s\nlimits: %s\nresids: %s" % (d, x, np.matrix(a).dot(x)-d.v)
        print ''


def sim_VSpeed():
    sim1 = VSF_sim()#0.12, 0.5)
    sim1.t1 = 100.0
    thrust = np.arange(145, 400, 50)
    start_v = np.arange(-100, 105, 100)
    def run_sim(c, n, v, vK=None):
        for t in thrust:
            sim1.run(v, maxV=1, thrust = t, vK=vK)
            sim1.plot_vs(2,c,n)
            sim1.plot_k(2,c,c+n)
    for i, v in enumerate(start_v):
        run_sim(len(start_v),i+1, v, sim1.vK2)
    sim1.legend()
    plt.show()
#end def

def sim_VS_Stability():
    sim1 = VSF_sim(0.12, 0.5)
    sim1.t1 = 20.0
    thrust = np.arange(45, 100, 10)
    imps = [1]#np.arange(-100, 105, 100)
    def run_sim(c, n, i):
        for t in thrust:
            sim1.run_impulse(i, 1.0, maxV=1, thrust = t)
            sim1.plot_vs(3,c,n)
            sim1.plot_k(3,c,c+n)
            sim1.plot_a(3,c,c*2+n)
    for n, imp in enumerate(imps):
        run_sim(len(imps),n+1, imp)
    sim1.legend()
    plt.show()
#end def
    
def sim_Altitude():
#     vs = loadCSV('VS-filtering-26.csv', ('AbsAlt', 'TerAlt', 'Alt', 'AltAhead', 'Err', 'VSP', 'aV', 'rV', 'dV'))
# #     ter = vs.TerAlt[-10:10:-1]
#     vs = vs[vs.Alt > 3]
#     ter = vs.TerAlt[17000:22000]
    
    sim1 = VSF_sim(AS=0.12, DS=0.5)
    sim1.t1 = 60.0
    thrust = [100] #np.arange(100, 300, 50)
    def run_sim(c, n, A, sA, pid):
        for t in thrust:
            sim1.run_alt(A, sA, thrust = t, pid = pid)
            i = 0; r = 7
            sim1.plot_alt( r, c, c*i+n); i += 1
            sim1.plot_ter( r, c, c*i+n); i += 1
            sim1.plot_ralt(r, c, c*i+n); i += 1
            sim1.plot_vs(  r, c, c*i+n); i += 1
            sim1.plot_vsp( r, c, c*i+n); i += 1
            sim1.plot_dvsp(r, c, c*i+n); i += 1
            sim1.plot_k(r, c, c*i+n); i += 1
            sim1.describe()
#     run_sim(2,1, 100.0, pid)
    run_sim(2,1, 50.0, 0.0, PID2(0.3, 0.0, 0.3, -9.9, 9.9))
    run_sim(2,2, 50.0, 105.0, PID2(0.3, 0.0, 0.3, -9.9, 9.9))
#    run_sim(4,3, -alt/10.0, pid)
#    run_sim(4,4, -alt, pid)
    sim1.legend()
    plt_show_maxed()
#end def

def legend():
    plt.legend(bbox_to_anchor=(1.01, 1), loc=2, borderaxespad=0.)

def sim_Rotation():
    def _plot(r, c, n, X, Y, aa, ylab):
        plt.subplot(r, c, n)
        plt.plot(X, Y, label=("V: AA=%.1f" % aa))
        plt.xlabel("time (s)")
        plt.ylabel(ylab)
    
    MaxAngularA = np.arange(0.5, 30, 5);
    start_error = 0.8*np.pi
    end_time = 10.0
    
    def test(c, n, pid):
        p = pid.kp; d = pid.kd
        for aa in MaxAngularA:
            A = [start_error]
            V = [0.0]
            S = [0.0]
            T = [0.0]
            def plot(c, n, Y, ylab):
                _plot(3, c, n, T, Y, aa, ylab)
            pid.kp = p/aa
            pid.kd = d/aa
            while T[-1] < end_time:
                S.append(pid.update(A[-1]))
                V.append(V[-1] - S[-1]*aa*dt)
                A.append(A[-1] + V[-1]*dt)
                T.append(T[-1]+dt)
            plot(c, n, np.fromiter(A, float)/np.pi*180.0, 'Angle')
            plot(c, c+n, V, 'Angular velocity')
            plot(c, c*2+n, S, 'Steering')
        
    test(2, 1, PID(6.0, 0, 10.0, -1, 1))
    test(2, 2, PID(4.0, 0, 6.0, -1, 1))
    legend()
    plt.show()
    
def drawVectors():
    from mpl_toolkits.mplot3d import Axes3D
    import matplotlib.lines as mlines
    
    
    x = (1,0,0); y = (0,1,0); z = (0,0,1)
    
    NoseUp = [
                (0.426938, 0.6627575, 0.6152045), #right
                (-0.9027369, 0.3521126, 0.2471495), #up
                (-0.05282113, -0.6608852, 0.7486259), #fwd
                (-0.825050456225237, 0.00142223040578914, 0.565057273153087), #Up
                vec(-40.7348866753984, 82.6265182495117, -60.7879408364129).norm.v, #vel
             ]
    
    NoseHor = [
                (0.9065102, 0.2023994, 0.3705047), #right
                (-0.4193277, 0.3297398, 0.8458344), #up
                (0.04902627, -0.9221203, 0.3837842), #fwd
                vec(-124.8083, 99.28588, 254.6226).norm.v, #-T
#                 vec(8.85797889364285, 42.9853324890137, 16.2476060788045).norm.v, #vel
#                 vec(14.74958, -277.06, 115.2648).norm.v, #[r*-T]
             ]
    
    LookAhead = [
                    (-0.853199320849177, 0.0880317238524617, 0.514102455253879), #Up
                    (0.4738491, -0.3380022, 0.8131552), #r
                    (0.7306709, -0.3828829, -0.5652617), #lookahead
                 ]
    
    GreatCircle = [
                   (-0.853199320849177, 0.0880317238524617, 0.514102455253879), #Up
                   (0.553682, -0.2360972, 0.7985577), #VDir0
                   (-0.4253684, -0.6641812, -0.6147562) #VDir0
                   ]
    
    GreatCircle = [
                   (0, 1, 0), #Up
                   (np.sin(-103.6567/180*np.pi), 0, np.cos(-103.6567/180*np.pi)) #VDir0
                   ]
    
    Radar = [
(0.4143046, -0.6872179, 0.5967271), #Dir
(0.615147, -0.6593181, 0.4323122), #d
(-0.821889802172869, -0.00085793802058045, 0.569645869840723), #Up
(0.3722304, 0.7262448, 0.5779386), #right
             ]
    
    MunNoseHor = [
(1, 0, 0),
(0, 1, 0),
(0.00198698, 0.999992, 0.003474206),
(-0.01996278, -0.1021231, -0.9945714),
(-0.0001221597, 0.9947699, -0.1021409),
(0.3317407, 0.9377342, -0.1029695),
                    ]
    
    def xzy(v): return v[0], v[2], v[1]
    
    def draw_vectors(*vecs):
        if not vecs: return;
        X, Y, Z, U, V, W = zip(*(xzy(v)+xzy(v) for v in vecs))
        colors = color_grad(len(vecs), 3)
        fig = plt.figure()
        ax = fig.gca(projection='3d')
        ax.quiver(X,Y,Z,U,V,W, colors=colors, lw=2, arrow_length_ratio=0.1)
        ax.set_xlim([-1,1])
        ax.set_ylim([-1,1])
        ax.set_zlim([-1,1])
        ax.set_xlabel('r')
        ax.set_ylabel('f')
        ax.set_zlabel('u')
        legends = []
        for i in xrange(len(vecs)):
            legends.append(mlines.Line2D([], [], color=colors[i*3], label=str(i+1)))
        plt.legend(handles=legends)
        plt.show()
    
#     draw_vectors(*NoseUp)
    draw_vectors(*MunNoseHor)
    
def color_grad(num, repeat=1):
    colors = [(0,1,0)]*repeat
    n = float(num)
    for i in xrange(1, num):
        c = (i/n, 1-i/n, 1-i/n)
        colors += (c,)*repeat
    return colors
    
def Gauss(old, cur, ratio = 0.7, poles = 2):
    for _i in xrange(poles):
        cur = (1-ratio)*old+ratio*cur
    return cur

def EWA(old, cur, ratio = 0.7):
    return (1-ratio)*old+ratio*cur

def EWA2(old, cur, ratio = 0.7):
    if cur < old: ratio = clamp01(1-ratio)
    return (1-ratio)*old+ratio*cur

def vFilter(v, flt, **kwargs):
    f = [v[0]]
    for val in v[:-1]:
        f.append(flt(f[-1], val, **kwargs))
    return np.fromiter(f, float)

def simFilters():
    df = loadCSV('VS-filtering-34.csv', ('AbsAlt', 'TerAlt', 'Alt', 'AltAhead', 'Err', 'VSP', 'VSF', 'MinVSF', 'aV', 'rV', 'dV', 'mdTWR', 'mTWR', 'hV'))
    df = df[df.Alt > 3].reset_index()
    addL(df)
    L = df.L
    a = df.TerAlt
    aa = df.AltAhead
#     t1 = 20
    T = np.arange(0, df.shape[0]*dt, dt)
#     er = np.sin(T*0.5)+np.random.normal(size=len(L))/10.0
    ewa = vFilter(aa, EWA, ratio=0.1)
    ewa2 = vFilter(aa, EWA2, ratio=0.9)
    ax = plt.subplot()
    ax1 = ax.twinx()
    ax.plot(T, a, label='Alt')
    ax1.plot(T, -aa, label='Rad')
    ax1.plot(T, -ewa, label='EWA')
    ax1.plot(T, -ewa2, label='EWA2')
#     ax1.plot(L, g2, label='Gauss2')
    legend()
    plt.show()
    
def simGC():
    import math as m
    
    class angle(object):
        def __init__(self, d=0, m=0, s=0):
            self.deg = d+m/60.0+s/3600.0
            self.rad = self.deg/180.0*np.pi
        
        def _update(self):
            self.deg = self.rad/m.pi*180.0
        
        @classmethod
        def from_rad(cls, rad):
            a = angle()
            a.rad = rad
            a._update()
            return a
        
        def __float__(self): return self.rad
        def __str__(self, *args, **kwargs): 
            return '%fd' % self.deg
        
        def __add__(self, a):
            a1 = self.from_rad(self.rad + a.rad)
            return a1
            
        def __sub__(self, a):
            a1 = self.from_rad(self.rad - a.rad)
            return a1
        
        def __mul__(self, r):
            a1 = self.from_rad(self.rad*r)
            return a1
            
    class point(object):
        def __init__(self, lat, lon):
            self.lat = lat
            self.lon = lon
            
        def __str__(self, *args, **kwargs):
            return 'lat: %s, lon: %s' % (self.lat, self.lon)
    
    def bearing(p1, p2):
        cos_lat2 = m.cos(p2.lat)
        dlon = p2.lon-p1.lon
        y = m.sin(dlon)*cos_lat2;
        x = m.cos(p1.lat)*m.sin(p2.lat) - m.sin(p1.lat)*cos_lat2*m.cos(dlon);
        return m.atan2(y, x)
    
    def point_between(p1, p2, dist):
        b = bearing(p1, p2);
        sin_dist = m.sin(dist);
        cos_dist = m.cos(dist);
        sin_lat1 = m.sin(p1.lat);
        cos_lat1 = m.cos(p1.lat);
        lat2 = m.asin(sin_lat1*cos_dist + cos_lat1*sin_dist*m.cos(b));
        dlon2 = m.atan2(m.sin(b)*sin_dist*cos_lat1, cos_dist-sin_lat1*m.sin(lat2));
        return point(angle.from_rad(lat2), 
                     angle.from_rad(p1.lon.rad+dlon2));
    
    p1 = point(angle(1,12,13), angle(284,30,41))
    p2 = point(angle(5,22,20), angle(254,58,00))
    
    r = 600000.0
    v = 100.0
    
    t = 0; dt = 0.01
    pt = p1; pa = p1
    while t < 2000:
        da = v*dt/r
        pt = point_between(pt, p2, da)
        ba = angle.from_rad(bearing(pa, p2))
        pa = point(pa.lat+angle.from_rad(da*m.cos(ba)), pa.lon+angle.from_rad(da*m.sin(ba)))
        t += dt
    
    print p1
    print pt
    print pa
    print (pa.lat-pt.lat).rad*r,(pa.lon-pt.lon).rad*r
    print p2
    
#     P = [p1]
#     for d in np.arange(0.01, 0.6, 0.01):
#         P.append(point_between(p1, p2, d))
#         print P[-1]
#     P.append(p2)
#     
#     lat = [p.lat.deg for p in P]
#     lon = [p.lon.deg for p in P]
#     
#     plt.plot(lon, lat, '*')
#     plt.show()


def loadCSV(filename, columns=None, header=None):
    os.chdir(os.path.join(os.environ['HOME'], 'ThrottleControlledAvionics', 'Tests'))
    df = pa.read_csv(filename, header=header, names=columns)
    return df

def drawDF(df, columns=None, colors=None, axes=None):
    from collections import Counter 
    l = df.shape[0]
    L = df.L if 'L' in df else np.arange(0, l, 1)
    cols = df.keys() if columns is None else columns
    num_axes = Counter(axes)
    nrows = max(num_axes.values())
    ncols = len(num_axes.keys())
    if colors is None: colors = color_grad(len(cols))
    for i, k in enumerate(cols):
        if axes is None:
            plt.plot(L, df[k], label=k, color=colors[i])
        else:
            plt.subplot(nrows, ncols, ncols*(i%nrows)+axes[i])
            plt.plot(L, df[k], label=k, color=colors[i])
            plt.ylabel(k)
#     plt.legend(bbox_to_anchor=(1.01, 1), loc=2, borderaxespad=0.0)
    plt_show_maxed()

def plt_show_maxed():
    plt.tight_layout(pad=0, h_pad=0, w_pad=0)
    plt.subplots_adjust(top=0.99, bottom=0.03, left=0.05, right=0.99, hspace=0.25, wspace = 0.1)
    mng = plt.get_current_fig_manager()
    mng.window.showMaximized()
    plt.show()

def boxplot(df, columns=None):
    cnames = df.keys() if columns is None else columns
    plt.boxplot([df[k] for k in cnames], labels=cnames)
    plt_show_maxed()
    
def describe(df, columns=None):
    from scipy import stats
    cnames = df.keys() if columns is None else columns
    for k in cnames:
        c = df[k] 
        d = stats.describe(c)
        print '%s:' % k
        print '   len:    ', len(c)
        print '   sum:    ', sum(c)
        print '   min-max:', d.minmax
        print '   mean:   ', d.mean
        print '   median: ', np.median(c)
        print '   std:    ', np.std(c)
        print '   sem:    ', stats.sem(c)
        print '   skew:   ', d.skewness
        print '   hist:   '
        h = np.histogram(c, normed=True)
        for i, e in enumerate(h[1][1:]):
            e0 = h[1][i]
            print '[% 8.3f : % 8.3f]: %s' %(e0, e, "#"*int(h[0][i]*80))
        print ''
    print '\n'
      
      
def addL(df):
    '''add horizontal coordinate column'''
    L = [0]
    if 'hV' in df:
        for hv in df.hV[:-1]:
            L.append(L[-1]+hv*dt) 
    else: 
        L = np.arange(0, df.shape[0], 1)
    df['L'] = pa.Series(L, index=df.index)
      
def analyzeCSV(filename, header, cols=None, region = None):
    df = loadCSV(filename, header)
    if 'Alt' in df:
        df = df[df.Alt > 3].reset_index()
    addL(df)
    #slice by L
    if region:
        region = list(region)
        if len(region) < 2: region.append(None)
        if region[0] == None: region[0] = 0
        if region[1] == None: region[1]  = df.L.last
        df = df[(df.L > region[0]) & (df.L <= region[1])]
#     describe(df)
#     print df.iloc[500]
    drawDF(df, cols, axes=[1]*(len(df.keys()) if cols is None else len(cols)))
  
  
def sim_PointNav():
    P = 2; D = 0.1
    pid = PID(P, 0, D, 0, 10)
    accel = np.arange(0.1, 1.1, 0.1);
    distance = 50
    distanceF = 1
    cols = color_grad(len(accel))
    for i, a in enumerate(accel):
        d = [distance]
        v = [0]
        act = [0]
        t = 0
        while d[-1] > 0.08:
            pid.kp = P*a/clampL(v[-1], 0.1)
            act.append(pid.update(d[-1]*distanceF))
            if v[-1] < pid.action:
                v.append(v[-1]+a*dt)
            elif v[-1] > pid.action:
                v.append(v[-1]-a*dt)
            else: v.append(v[-1])
            d.append(d[-1]-v[-1]*dt)
            t += dt
        print 'accel=%.2f, time: %.1fs' % (a, t)
        plt.subplot(2, 1, 1)
        plt.plot(d, v, color=cols[i], label="accel=%.2f"%a)
        plt.ylabel("V"); plt.xlabel("distance")
        plt.subplot(2, 1, 2)
        plt.plot(d, act, color=cols[i], label="accel=%.2f"%a)
        plt.ylabel("act"); plt.xlabel("distance")
    plt.legend()
    plt_show_maxed()
#==================================================================#

dt = 0.05

if __name__ == '__main__':
#     sim_VSpeed()
#     sim_VS_Stability()
#     sim_Altitude()
#     sim_Attitude()
#     sim_Rotation()
#     simFilters()
#     simGC()
#     analyzeCSV('VS-filtering-43.csv',
#                ('AbsAlt', 'TerAlt', 'Alt', 'AltAhead', 'Err', 'VSP', 'VSF', 'MinVSF', 'aV', 'rV', 'dV', 'mdTWR', 'mTWR', 'hV'),
#                 ('AbsAlt', 'TerAlt', 'Alt', 'AltAhead', 'Err', 'VSP', 'VSF', 'aV', 'rV', 'dV', 'mdTWR', 'hV'))
#                 ('Alt', 'Err', 'VSP', 'VSF', 'dV'))
# #                ['AltAhead']
#                 , (13,))
    
#     analyzeCSV('VS-filtering-39.csv',
#                ('BestAlt', 'DetAlt', 'AltAhead')
#                )
#     drawVectors()
    sim_PointNav()