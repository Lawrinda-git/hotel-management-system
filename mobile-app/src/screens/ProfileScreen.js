import React from 'react';
import { View, Text, TouchableOpacity } from 'react-native';

const ProfileScreen = ({ navigation }) => {
  return (
    <View style={{ flex: 1, backgroundColor: '#f7f9fb', padding: 20 }}>
      <Text style={{ fontSize: 20, fontWeight: '600', color: '#00288e', marginBottom: 20 }}>
        Profile
      </Text>
      
      <View style={{ backgroundColor: '#ffffff', borderRadius: 16, padding: 20, elevation: 2 }}>
        <Text style={{ fontSize: 16, color: '#191c1e' }}>Name: Guest User</Text>
        <Text style={{ color: '#444653', marginTop: 8 }}>Email: user@example.com</Text>
        <Text style={{ color: '#444653', marginTop: 8 }}>Phone: +233 24 123 4567</Text>
      </View>
      
      <TouchableOpacity 
        style={{ 
          backgroundColor: '#ffdad6', 
          borderRadius: 12, 
          padding: 16, 
          alignItems: 'center', 
          marginTop: 20 
        }}
        onPress={() => navigation.replace('Login')}
      >
        <Text style={{ color: '#ba1a1a', fontWeight: '600' }}>Logout</Text>
      </TouchableOpacity>
    </View>
  );
};

export default ProfileScreen;